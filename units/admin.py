from django.contrib import admin

from .models import Fighter, Fight, FightTurn


@admin.register(Fighter)
class FighterAdmin(admin.ModelAdmin):
    list_display = ("name", "unit_type", "team", "health", "attack_points")
    list_filter = ("team", "unit_type")


class FightTurnInline(admin.TabularInline):
    model = FightTurn
    extra = 0
    readonly_fields = ("turn_number", "attacker", "defender", "damage", "attacker_health", "defender_health")


@admin.register(Fight)
class FightAdmin(admin.ModelAdmin):
    list_display = ("id", "first_fighter", "second_fighter", "winner", "is_stalemate", "created_at")
    inlines = [FightTurnInline]
