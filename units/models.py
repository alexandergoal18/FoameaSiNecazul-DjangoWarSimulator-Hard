from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Fighter(models.Model):
    class UnitType(models.TextChoices):
        INFANTRY = "infantry", "Infantry"
        CANNON = "cannon", "Cannon"
        CAVALRY = "cavalry", "Cavalry"
        KNIGHT = "knight", "Knight"

    class Team(models.TextChoices):
        BLUE = "blue", "Blue"
        RED = "red", "Red"

    name = models.CharField(max_length=100)
    unit_type = models.CharField(max_length=16, choices=UnitType.choices)
    team = models.CharField(max_length=8, choices=Team.choices)
    health = models.PositiveSmallIntegerField(
        default=100, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    attack_points = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(50)]
    )
    profile_image_link = models.URLField()

    class Meta:
        ordering = ["name", "pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(health__gte=0) & models.Q(health__lte=100), name="fighter_health_range"),
            models.CheckConstraint(condition=models.Q(attack_points__gte=0) & models.Q(attack_points__lte=50), name="fighter_attack_range"),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_team_display()} {self.get_unit_type_display()})"


class Fight(models.Model):
    first_fighter = models.ForeignKey(Fighter, on_delete=models.PROTECT, related_name="fights_started")
    second_fighter = models.ForeignKey(Fighter, on_delete=models.PROTECT, related_name="fights_received")
    winner = models.ForeignKey(
        Fighter, null=True, blank=True, on_delete=models.SET_NULL, related_name="won_fights"
    )
    is_stalemate = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"Fight #{self.pk}: {self.first_fighter.name} vs {self.second_fighter.name}"


class FightTurn(models.Model):
    fight = models.ForeignKey(Fight, on_delete=models.CASCADE, related_name="turns")
    turn_number = models.PositiveIntegerField()
    attacker = models.ForeignKey(Fighter, on_delete=models.PROTECT, related_name="attacks_made")
    defender = models.ForeignKey(Fighter, on_delete=models.PROTECT, related_name="attacks_received")
    damage = models.PositiveSmallIntegerField()
    attacker_health = models.PositiveSmallIntegerField()
    defender_health = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["turn_number"]
        constraints = [models.UniqueConstraint(fields=["fight", "turn_number"], name="unique_turn_per_fight")]

    def __str__(self):
        return f"Fight #{self.fight_id}, turn {self.turn_number}"
