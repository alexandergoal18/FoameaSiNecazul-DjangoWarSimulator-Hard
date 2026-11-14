from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import BatchStatus, ChallengeRun, DraftBatch, FightBatch, FightStep, ImportedFight, Person
from .tasks import apply_draft_batch, fetch_draft_batch, import_fight, replay_fight


class HardChallengeFactoryMixin:
    def person(self, external_id, name, *, health=None, rank=None):
        return Person.objects.create(
            external_id=external_id, name=name, age=30, health=health, rank=rank
        )

    def fight_payload(self, fight_id=10, blue_id=1, red_id=2):
        return {
            "fight_id": fight_id,
            "blue_soldier_id": blue_id,
            "red_soldier_id": red_id,
            "steps": [
                {"attacker": blue_id, "defender": red_id, "damage": 30},
                {"attacker": red_id, "defender": blue_id, "damage": 10},
            ],
        }


class HardChallengeTaskTests(HardChallengeFactoryMixin, TestCase):
    def test_draft_batch_populates_rank_and_starting_health(self):
        person = self.person(1, "Brody Sanchez")
        run = ChallengeRun.objects.create()
        batch = DraftBatch.objects.create(run=run, remote_index=0, status=BatchStatus.DOWNLOADED)
        payload = [{"id": 1, "name": "Brody Sanchez", "age": 21, "rank": "Lieutenant", "health": 100}]

        result = apply_draft_batch.apply(args=[batch.pk, payload]).get()

        person.refresh_from_db()
        batch.refresh_from_db()
        self.assertEqual(result["drafted"], 1)
        self.assertEqual(person.rank, "Lieutenant")
        self.assertEqual(person.health, 100)
        self.assertIsNotNone(person.drafted_at)
        self.assertEqual(batch.status, BatchStatus.COMPLETED)

    def test_fight_import_and_duplicate_delivery_store_steps_once(self):
        blue = self.person(1, "Blue", health=100, rank="Private")
        red = self.person(2, "Red", health=100, rank="General")
        run = ChallengeRun.objects.create()
        batch = FightBatch.objects.create(run=run, remote_index=0)
        payload = self.fight_payload()

        first = import_fight.apply(args=[batch.pk, payload]).get()
        second = import_fight.apply(args=[batch.pk, payload]).get()

        fight = ImportedFight.objects.get(remote_fight_id=10)
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(fight.blue_soldier, blue)
        self.assertEqual(fight.red_soldier, red)
        self.assertEqual(FightStep.objects.filter(fight=fight).count(), 2)

    def test_replay_applies_source_steps_once_and_records_health(self):
        blue = self.person(1, "Blue", health=100, rank="Private")
        red = self.person(2, "Red", health=100, rank="General")
        run = ChallengeRun.objects.create()
        batch = FightBatch.objects.create(run=run, remote_index=0)
        import_fight.apply(args=[batch.pk, self.fight_payload()]).get()
        fight = ImportedFight.objects.get(remote_fight_id=10)

        replay_fight.apply(args=[fight.pk]).get()
        replay_fight.apply(args=[fight.pk]).get()

        blue.refresh_from_db()
        red.refresh_from_db()
        fight.refresh_from_db()
        self.assertEqual(blue.health, 90)
        self.assertEqual(red.health, 70)
        self.assertEqual(fight.replay_status, ImportedFight.ReplayStatus.COMPLETED)
        self.assertEqual(list(fight.steps.values_list("defender_health_after", flat=True)), [70, 90])

    @patch("hardchallenge.tasks.apply_draft_batch.delay")
    @patch("hardchallenge.tasks.fetch_draft_batch.delay")
    @patch("hardchallenge.tasks.ChallengeClient")
    def test_draft_page_queues_next_page_before_local_application(self, client_class, next_delay, apply_delay):
        run = ChallengeRun.objects.create()
        client_class.return_value.draft_batch.return_value = {
            "data": [{"id": 1, "name": "Brody", "age": 21, "rank": "Private", "health": 100}],
            "next_batch": 1,
            "status": 200,
        }

        fetch_draft_batch.apply(args=[run.pk, 0]).get()

        batch = DraftBatch.objects.get(run=run, remote_index=0)
        self.assertEqual(batch.status, BatchStatus.DOWNLOADED)
        next_delay.assert_called_once_with(run.pk, 1)
        apply_delay.assert_called_once_with(batch.pk, client_class.return_value.draft_batch.return_value["data"])


class HardChallengeViewTests(TestCase):
    def test_index_links_to_hard_challenge_pages(self):
        response = self.client.get("/")

        self.assertContains(response, reverse("units:all"))
        self.assertContains(response, reverse("hardchallenge:dashboard"))
        self.assertContains(response, reverse("hardchallenge:simulate"))

    @patch("hardchallenge.views.import_people_and_start_pipelines.delay")
    def test_dashboard_starts_background_import(self, delay):
        response = self.client.post(reverse("hardchallenge:start_import"))

        self.assertRedirects(response, reverse("hardchallenge:dashboard"))
        run = ChallengeRun.objects.get()
        delay.assert_called_once_with(run.pk)

    def test_simulate_page_renders_imported_fight(self):
        blue = Person.objects.create(external_id=1, name="Blue", age=20, health=100, rank="Private")
        red = Person.objects.create(external_id=2, name="Red", age=20, health=100, rank="General")
        ImportedFight.objects.create(remote_fight_id=1, blue_soldier=blue, red_soldier=red)

        response = self.client.get(reverse("hardchallenge:simulate"))

        self.assertContains(response, "Blue")
        self.assertContains(response, "Queue eligible fights")
