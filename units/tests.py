from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .forms import FightForm
from .models import Fighter, Fight, FightTurn
from .services import simulate_fight


class FighterFactoryMixin:
    def fighter(self, name, team, *, health=100, attack_points=10):
        return Fighter.objects.create(
            name=name,
            unit_type=Fighter.UnitType.KNIGHT,
            team=team,
            health=health,
            attack_points=attack_points,
            profile_image_link="https://example.com/fighter.png",
        )


class FightSimulationTests(FighterFactoryMixin, TestCase):
    @patch("units.services.random.randint", return_value=10)
    def test_simulation_persists_turns_winner_and_health(self, mocked_randint):
        blue = self.fighter("Blue knight", Fighter.Team.BLUE, health=10)
        red = self.fighter("Red knight", Fighter.Team.RED, health=10)

        fight = simulate_fight(blue, red)

        blue.refresh_from_db()
        red.refresh_from_db()
        turn = FightTurn.objects.get(fight=fight)
        self.assertEqual(fight.winner, blue)
        self.assertEqual(red.health, 0)
        self.assertEqual(turn.damage, 10)
        self.assertEqual(turn.attacker_health, 10)
        self.assertEqual(turn.defender_health, 0)
        mocked_randint.assert_called_once_with(0, 10)

    def test_zero_attack_points_on_both_sides_creates_stalemate(self):
        blue = self.fighter("Blue", Fighter.Team.BLUE, attack_points=0)
        red = self.fighter("Red", Fighter.Team.RED, attack_points=0)

        fight = simulate_fight(blue, red)

        self.assertTrue(fight.is_stalemate)
        self.assertIsNone(fight.winner)
        self.assertFalse(FightTurn.objects.filter(fight=fight).exists())


class UnitViewsTests(FighterFactoryMixin, TestCase):
    def test_creation_list_and_healing_flow(self):
        response = self.client.post(
            reverse("units:create"),
            {
                "name": "Scout",
                "unit_type": Fighter.UnitType.CAVALRY,
                "team": Fighter.Team.BLUE,
                "health": 44,
                "attack_points": 12,
                "profile_image_link": "https://example.com/scout.png",
            },
        )
        fighter = Fighter.objects.get(name="Scout")
        self.assertRedirects(response, reverse("units:all"))

        response = self.client.get(reverse("units:all"))
        self.assertContains(response, "Scout")
        self.assertContains(response, "Team statistics")

        response = self.client.post(reverse("units:heal", args=[fighter.pk]))
        fighter.refresh_from_db()
        self.assertRedirects(response, reverse("units:all"))
        self.assertEqual(fighter.health, 100)

    def test_fight_form_rejects_same_team(self):
        first = self.fighter("Blue one", Fighter.Team.BLUE)
        second = self.fighter("Blue two", Fighter.Team.BLUE)

        form = FightForm({"first_fighter": first.pk, "second_fighter": second.pk})

        self.assertFalse(form.is_valid())
        self.assertIn("different teams", form.non_field_errors()[0])

    def test_detail_page_edits_fighter(self):
        fighter = self.fighter("Original", Fighter.Team.BLUE, health=40, attack_points=8)

        response = self.client.post(
            reverse("units:detail", args=[fighter.pk]),
            {
                "name": "Updated",
                "unit_type": Fighter.UnitType.CANNON,
                "team": Fighter.Team.RED,
                "health": 75,
                "attack_points": 25,
                "profile_image_link": "https://example.com/updated.png",
            },
        )

        fighter.refresh_from_db()
        self.assertRedirects(response, reverse("units:detail", args=[fighter.pk]))
        self.assertEqual(fighter.name, "Updated")
        self.assertEqual(fighter.team, Fighter.Team.RED)
        self.assertEqual(fighter.health, 75)

    def test_delete_removes_fighter_and_its_history(self):
        blue = self.fighter("Blue", Fighter.Team.BLUE, health=10)
        red = self.fighter("Red", Fighter.Team.RED, health=10)
        with patch("units.services.random.randint", return_value=10):
            fight = simulate_fight(blue, red)

        response = self.client.post(reverse("units:delete", args=[blue.pk]))

        self.assertRedirects(response, reverse("units:all"))
        self.assertFalse(Fighter.objects.filter(pk=blue.pk).exists())
        self.assertFalse(Fight.objects.filter(pk=fight.pk).exists())
        self.assertEqual(FightTurn.objects.count(), 0)
