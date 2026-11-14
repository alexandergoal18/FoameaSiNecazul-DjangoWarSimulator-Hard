import random

from django.db import transaction

from .models import Fight, FightTurn, Fighter


@transaction.atomic
def simulate_fight(first_fighter: Fighter, second_fighter: Fighter) -> Fight:
    """Run alternating attacks and persist every turn as it happens."""
    fighters = list(
        Fighter.objects.select_for_update().filter(pk__in=[first_fighter.pk, second_fighter.pk]).order_by("pk")
    )
    locked = {fighter.pk: fighter for fighter in fighters}
    first = locked[first_fighter.pk]
    second = locked[second_fighter.pk]

    fight = Fight.objects.create(first_fighter=first, second_fighter=second)
    if first.attack_points == 0 and second.attack_points == 0:
        fight.is_stalemate = True
        fight.save(update_fields=["is_stalemate"])
        return fight

    attacker, defender = first, second
    turn_number = 1
    while first.health > 0 and second.health > 0:
        damage = random.randint(0, attacker.attack_points)
        defender.health = max(0, defender.health - damage)
        defender.save(update_fields=["health"])
        FightTurn.objects.create(
            fight=fight,
            turn_number=turn_number,
            attacker=attacker,
            defender=defender,
            damage=damage,
            attacker_health=attacker.health,
            defender_health=defender.health,
        )
        if defender.health == 0:
            fight.winner = attacker
            fight.save(update_fields=["winner"])
            break
        attacker, defender = defender, attacker
        turn_number += 1
    return fight
