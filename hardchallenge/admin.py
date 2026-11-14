from django.contrib import admin

from .models import ChallengeRun, DraftBatch, FightBatch, FightStep, ImportedFight, Person


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("external_id", "name", "age", "rank", "health", "drafted_at")
    search_fields = ("name", "external_id")
    list_filter = ("rank",)


@admin.register(ChallengeRun)
class ChallengeRunAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "people_count", "created_at", "completed_at")


@admin.register(DraftBatch)
class DraftBatchAdmin(admin.ModelAdmin):
    list_display = ("remote_index", "status", "person_count", "next_batch")


@admin.register(FightBatch)
class FightBatchAdmin(admin.ModelAdmin):
    list_display = ("remote_index", "status", "fight_count", "next_batch")


class FightStepInline(admin.TabularInline):
    model = FightStep
    extra = 0
    readonly_fields = ("step_number", "attacker", "defender", "damage", "defender_health_after")


@admin.register(ImportedFight)
class ImportedFightAdmin(admin.ModelAdmin):
    list_display = ("remote_fight_id", "blue_soldier", "red_soldier", "import_status", "replay_status")
    inlines = [FightStepInline]
