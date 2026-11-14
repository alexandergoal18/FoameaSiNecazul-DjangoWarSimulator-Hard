from billiard.exceptions import SoftTimeLimitExceeded
from celery import shared_task
from django.db import OperationalError, transaction
from django.utils import timezone

from .client import ChallengeClient, RemoteChallengeError
from .models import BatchStatus, ChallengeRun, DraftBatch, FightBatch, FightStep, ImportedFight, Person


RETRYABLE = (RemoteChallengeError, OperationalError, SoftTimeLimitExceeded)
RETRY_OPTIONS = {
    "autoretry_for": RETRYABLE,
    "retry_backoff": True,
    "retry_jitter": True,
    "retry_kwargs": {"max_retries": 5},
    "soft_time_limit": 110,
    "time_limit": 120,
}


@shared_task(bind=True, **RETRY_OPTIONS)
def import_people_and_start_pipelines(self, run_id):
    """Import the people register, then begin both cursor-based pipelines."""
    run = ChallengeRun.objects.get(pk=run_id)
    run.status = ChallengeRun.Status.RUNNING
    run.detail = "Downloading the people register."
    run.save(update_fields=["status", "detail"])
    try:
        people = ChallengeClient().people()
        with transaction.atomic():
            for data in people:
                external_id = _positive_int(data, "id", "person")
                age = _positive_int(data, "age", "person")
                name = data.get("name")
                if not isinstance(name, str) or not name.strip():
                    raise RemoteChallengeError("Every person needs a non-empty name.")
                Person.objects.update_or_create(
                    external_id=external_id,
                    defaults={"name": name.strip(), "age": age},
                )

        fetch_draft_batch.delay(run.pk, 0)
        fetch_fight_batch.delay(run.pk, 0)
        run.people_count = len(people)
        run.status = ChallengeRun.Status.COMPLETED
        run.detail = "People imported; drafting and fight pages are loading in background workers."
        run.completed_at = timezone.now()
        run.save(update_fields=["people_count", "status", "detail", "completed_at"])
        return {"people": len(people)}
    except Exception as exc:
        run.status = ChallengeRun.Status.FAILED
        run.detail = str(exc)
        run.save(update_fields=["status", "detail"])
        raise


@shared_task(bind=True, **RETRY_OPTIONS)
def fetch_draft_batch(self, run_id, remote_index):
    """Download one draft page and queue independent application work for it."""
    batch, _ = DraftBatch.objects.get_or_create(run_id=run_id, remote_index=remote_index)
    if batch.status == BatchStatus.COMPLETED:
        return {"batch": remote_index, "state": "completed"}
    try:
        batch.status = BatchStatus.DOWNLOADING
        batch.error_detail = ""
        batch.save(update_fields=["status", "error_detail"])
        payload = ChallengeClient().draft_batch(remote_index)
        people = payload["data"]
        next_batch = _next_batch(payload)
        batch.next_batch = next_batch
        batch.person_count = len(people)
        batch.status = BatchStatus.DOWNLOADED
        batch.downloaded_at = timezone.now()
        batch.save(update_fields=["next_batch", "person_count", "status", "downloaded_at"])

        # The next remote request need not wait for local drafting of this page.
        if next_batch is not None:
            fetch_draft_batch.delay(run_id, next_batch)
        apply_draft_batch.delay(batch.pk, people)
        return {"batch": remote_index, "people": len(people), "next_batch": next_batch}
    except Exception as exc:
        batch.status = BatchStatus.FAILED
        batch.error_detail = str(exc)
        batch.save(update_fields=["status", "error_detail"])
        raise


@shared_task(bind=True, **RETRY_OPTIONS)
def apply_draft_batch(self, batch_id, people):
    """Draft a downloaded page in its own task, as required by the challenge."""
    batch = DraftBatch.objects.get(pk=batch_id)
    if batch.status == BatchStatus.COMPLETED:
        return {"batch": batch.remote_index, "drafted": 0}
    try:
        with transaction.atomic():
            batch = DraftBatch.objects.select_for_update().get(pk=batch_id)
            if batch.status == BatchStatus.COMPLETED:
                return {"batch": batch.remote_index, "drafted": 0}
            batch.status = BatchStatus.PROCESSING
            batch.save(update_fields=["status"])
            ids = {_positive_int(data, "id", "draft person") for data in people}
            locked_people = {
                person.external_id: person
                for person in Person.objects.select_for_update().filter(external_id__in=ids).order_by("pk")
            }
            missing = ids - locked_people.keys()
            if missing:
                raise RemoteChallengeError(f"Draft batch references unknown people: {sorted(missing)}.")
            now = timezone.now()
            for data in people:
                person = locked_people[_positive_int(data, "id", "draft person")]
                rank = data.get("rank")
                if not isinstance(rank, str) or not rank.strip():
                    raise RemoteChallengeError("Every drafted person needs a rank.")
                person.name = str(data.get("name", person.name)).strip()
                person.age = _positive_int(data, "age", "draft person")
                person.rank = rank.strip()
                person.health = _positive_int(data, "health", "draft person")
                person.drafted_at = now
                person.save(update_fields=["name", "age", "rank", "health", "drafted_at"])
            batch.status = BatchStatus.COMPLETED
            batch.completed_at = now
            batch.error_detail = ""
            batch.save(update_fields=["status", "completed_at", "error_detail"])
        return {"batch": batch.remote_index, "drafted": len(people)}
    except Exception as exc:
        DraftBatch.objects.filter(pk=batch_id).update(status=BatchStatus.FAILED, error_detail=str(exc))
        raise


@shared_task(bind=True, **RETRY_OPTIONS)
def fetch_fight_batch(self, run_id, remote_index):
    """Download a fight page, advance the cursor, and fan out one task per fight."""
    batch, _ = FightBatch.objects.get_or_create(run_id=run_id, remote_index=remote_index)
    if batch.status == BatchStatus.COMPLETED:
        return {"batch": remote_index, "state": "completed"}
    try:
        batch.status = BatchStatus.DOWNLOADING
        batch.error_detail = ""
        batch.save(update_fields=["status", "error_detail"])
        payload = ChallengeClient().fight_batch(remote_index)
        fights = payload["data"]
        next_batch = _next_batch(payload)
        batch.next_batch = next_batch
        batch.fight_count = len(fights)
        batch.status = BatchStatus.DOWNLOADED
        batch.downloaded_at = timezone.now()
        batch.save(update_fields=["next_batch", "fight_count", "status", "downloaded_at"])

        # Follow the cursor immediately; imports from this page continue in parallel.
        if next_batch is not None:
            fetch_fight_batch.delay(run_id, next_batch)
        for fight in fights:
            import_fight.delay(batch.pk, fight)
        batch.status = BatchStatus.COMPLETED
        batch.save(update_fields=["status"])
        return {"batch": remote_index, "fights": len(fights), "next_batch": next_batch}
    except Exception as exc:
        batch.status = BatchStatus.FAILED
        batch.error_detail = str(exc)
        batch.save(update_fields=["status", "error_detail"])
        raise


@shared_task(bind=True, **RETRY_OPTIONS)
def import_fight(self, batch_id, data):
    """Persist one remote fight plus every ordered event exactly once."""
    remote_id = _positive_int(data, "fight_id", "fight")
    try:
        with transaction.atomic():
            existing = ImportedFight.objects.filter(remote_fight_id=remote_id).first()
            if existing:
                return {"fight": remote_id, "created": False}
            blue_id = _positive_int(data, "blue_soldier_id", "fight")
            red_id = _positive_int(data, "red_soldier_id", "fight")
            if blue_id == red_id:
                raise RemoteChallengeError("A fight cannot use the same person for both sides.")
            people = {
                person.external_id: person
                for person in Person.objects.filter(external_id__in=[blue_id, red_id])
            }
            if set(people) != {blue_id, red_id}:
                raise RemoteChallengeError("Fight references an unknown person.")
            steps = data.get("steps")
            if not isinstance(steps, list):
                raise RemoteChallengeError("Every fight needs a steps list.")
            fight = ImportedFight.objects.create(
                remote_fight_id=remote_id,
                batch_id=batch_id,
                blue_soldier=people[blue_id],
                red_soldier=people[red_id],
                import_status=ImportedFight.ImportStatus.IMPORTING,
            )
            step_rows = []
            allowed_ids = {blue_id, red_id}
            for number, step in enumerate(steps, start=1):
                attacker_id = _positive_int(step, "attacker", "fight step")
                defender_id = _positive_int(step, "defender", "fight step")
                damage = _non_negative_int(step, "damage", "fight step")
                if attacker_id not in allowed_ids or defender_id not in allowed_ids or attacker_id == defender_id:
                    raise RemoteChallengeError("A fight step must use the two people in its fight.")
                step_rows.append(
                    FightStep(
                        fight=fight,
                        step_number=number,
                        attacker=people[attacker_id],
                        defender=people[defender_id],
                        damage=damage,
                    )
                )
            FightStep.objects.bulk_create(step_rows)
            fight.import_status = ImportedFight.ImportStatus.COMPLETED
            fight.imported_at = timezone.now()
            fight.save(update_fields=["import_status", "imported_at"])
            return {"fight": remote_id, "created": True}
    except Exception as exc:
        ImportedFight.objects.filter(remote_fight_id=remote_id).update(
            import_status=ImportedFight.ImportStatus.FAILED, error_detail=str(exc)
        )
        raise


@shared_task(bind=True, **RETRY_OPTIONS)
def replay_fight(self, fight_id):
    """Apply a fight's stored steps under row locks so shared people stay consistent."""
    try:
        with transaction.atomic():
            fight = ImportedFight.objects.select_for_update().get(pk=fight_id)
            if fight.import_status != ImportedFight.ImportStatus.COMPLETED:
                raise RemoteChallengeError("Fight events are not fully imported.")
            if fight.replay_status == ImportedFight.ReplayStatus.COMPLETED:
                return {"fight": fight.remote_fight_id, "replayed": False}
            people = {
                person.pk: person
                for person in Person.objects.select_for_update()
                .filter(pk__in=[fight.blue_soldier_id, fight.red_soldier_id])
                .order_by("pk")
            }
            if len(people) != 2 or any(person.health is None for person in people.values()):
                raise RemoteChallengeError("Both people must be drafted before their fight is replayed.")
            fight.replay_status = ImportedFight.ReplayStatus.RUNNING
            fight.error_detail = ""
            fight.save(update_fields=["replay_status", "error_detail"])
            for step in fight.steps.select_for_update().order_by("step_number"):
                defender = people[step.defender_id]
                defender.health = max(0, defender.health - step.damage)
                defender.save(update_fields=["health"])
                step.defender_health_after = defender.health
                step.save(update_fields=["defender_health_after"])
            fight.replay_status = ImportedFight.ReplayStatus.COMPLETED
            fight.replayed_at = timezone.now()
            fight.save(update_fields=["replay_status", "replayed_at"])
            return {"fight": fight.remote_fight_id, "replayed": True}
    except Exception as exc:
        ImportedFight.objects.filter(pk=fight_id).exclude(
            replay_status=ImportedFight.ReplayStatus.COMPLETED
        ).update(replay_status=ImportedFight.ReplayStatus.FAILED, error_detail=str(exc))
        raise


def _next_batch(payload):
    value = payload.get("next_batch")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RemoteChallengeError("next_batch must be a non-negative integer or null.")
    return value


def _positive_int(data, key, label):
    value = data.get(key) if isinstance(data, dict) else None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RemoteChallengeError(f"{label} field {key!r} must be a non-negative integer.")
    return value


def _non_negative_int(data, key, label):
    return _positive_int(data, key, label)
