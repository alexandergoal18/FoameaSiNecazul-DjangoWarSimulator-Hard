from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import ChallengeRun, ImportedFight, Person
from .tasks import import_people_and_start_pipelines, replay_fight


def dashboard(request):
    latest_run = ChallengeRun.objects.first()
    return render(
        request,
        "hardchallenge/dashboard.html",
        {
            "latest_run": latest_run,
            "people_count": Person.objects.count(),
            "drafted_count": Person.objects.exclude(rank__isnull=True).count(),
            "fight_count": ImportedFight.objects.count(),
            "imported_fight_count": ImportedFight.objects.filter(
                import_status=ImportedFight.ImportStatus.COMPLETED
            ).count(),
        },
    )


@require_POST
def start_import(request):
    run = ChallengeRun.objects.create()
    try:
        import_people_and_start_pipelines.delay(run.pk)
    except Exception as exc:
        run.status = ChallengeRun.Status.FAILED
        run.detail = f"Could not queue import: {exc}"
        run.save(update_fields=["status", "detail"])
        messages.error(request, run.detail)
    else:
        messages.success(request, "Import queued. Refresh the dashboard to see progress.")
    return redirect("hardchallenge:dashboard")


def people(request):
    return render(request, "hardchallenge/people.html", {"people": Person.objects.all()})


def fights(request):
    fight_list = (
        ImportedFight.objects.select_related("blue_soldier", "red_soldier")
        .annotate(step_count=Count("steps"))
    )
    return render(request, "hardchallenge/fights.html", {"fights": fight_list})


def fight_detail(request, pk):
    fight = get_object_or_404(
        ImportedFight.objects.select_related("blue_soldier", "red_soldier"), pk=pk
    )
    steps = fight.steps.select_related("attacker", "defender")
    return render(request, "hardchallenge/fight_detail.html", {"fight": fight, "steps": steps})


def simulate(request):
    fight_list = ImportedFight.objects.select_related("blue_soldier", "red_soldier")
    return render(request, "hardchallenge/simulate.html", {"fights": fight_list})


@require_POST
def start_simulation(request):
    fights = ImportedFight.objects.filter(
        import_status=ImportedFight.ImportStatus.COMPLETED,
        replay_status__in=[ImportedFight.ReplayStatus.PENDING, ImportedFight.ReplayStatus.FAILED],
    )
    ids = list(fights.values_list("pk", flat=True))
    fights.update(replay_status=ImportedFight.ReplayStatus.QUEUED, error_detail="")
    try:
        for fight_id in ids:
            replay_fight.delay(fight_id)
    except Exception:
        ImportedFight.objects.filter(pk__in=ids).update(replay_status=ImportedFight.ReplayStatus.FAILED)
        messages.error(request, "Could not queue fight replays. Check Redis and the Celery worker.")
    else:
        messages.success(request, f"Queued {len(ids)} fight replay(s).")
    return redirect("hardchallenge:simulate")
