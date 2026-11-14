# Generated for the hard challenge.

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ChallengeRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], default="queued", max_length=16)),
                ("people_count", models.PositiveIntegerField(default=0)),
                ("detail", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
        migrations.CreateModel(
            name="Person",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.PositiveIntegerField(unique=True)),
                ("name", models.CharField(max_length=255)),
                ("age", models.PositiveSmallIntegerField()),
                ("rank", models.CharField(blank=True, max_length=100, null=True)),
                ("health", models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ("drafted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["external_id"]},
        ),
        migrations.CreateModel(
            name="DraftBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("remote_index", models.PositiveIntegerField()),
                ("next_batch", models.PositiveIntegerField(blank=True, null=True)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("downloading", "Downloading"), ("downloaded", "Downloaded"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed")], default="queued", max_length=16)),
                ("person_count", models.PositiveIntegerField(default=0)),
                ("error_detail", models.TextField(blank=True)),
                ("downloaded_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="draft_batches", to="hardchallenge.challengerun")),
            ],
            options={"ordering": ["remote_index"]},
        ),
        migrations.CreateModel(
            name="FightBatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("remote_index", models.PositiveIntegerField()),
                ("next_batch", models.PositiveIntegerField(blank=True, null=True)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("downloading", "Downloading"), ("downloaded", "Downloaded"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed")], default="queued", max_length=16)),
                ("fight_count", models.PositiveIntegerField(default=0)),
                ("error_detail", models.TextField(blank=True)),
                ("downloaded_at", models.DateTimeField(blank=True, null=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="fight_batches", to="hardchallenge.challengerun")),
            ],
            options={"ordering": ["remote_index"]},
        ),
        migrations.CreateModel(
            name="ImportedFight",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("remote_fight_id", models.PositiveIntegerField(unique=True)),
                ("import_status", models.CharField(choices=[("queued", "Queued"), ("importing", "Importing"), ("completed", "Completed"), ("failed", "Failed")], default="queued", max_length=16)),
                ("replay_status", models.CharField(choices=[("pending", "Pending"), ("queued", "Queued"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed")], default="pending", max_length=16)),
                ("error_detail", models.TextField(blank=True)),
                ("imported_at", models.DateTimeField(blank=True, null=True)),
                ("replayed_at", models.DateTimeField(blank=True, null=True)),
                ("batch", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="fights", to="hardchallenge.fightbatch")),
                ("blue_soldier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="blue_fights", to="hardchallenge.person")),
                ("red_soldier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="red_fights", to="hardchallenge.person")),
            ],
            options={"ordering": ["remote_fight_id"]},
        ),
        migrations.CreateModel(
            name="FightStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("step_number", models.PositiveIntegerField()),
                ("damage", models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(0)])),
                ("defender_health_after", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("attacker", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attacks", to="hardchallenge.person")),
                ("defender", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="defences", to="hardchallenge.person")),
                ("fight", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="hardchallenge.importedfight")),
            ],
            options={"ordering": ["step_number"]},
        ),
        migrations.AddConstraint(
            model_name="draftbatch",
            constraint=models.UniqueConstraint(fields=("run", "remote_index"), name="unique_draft_batch_per_run"),
        ),
        migrations.AddConstraint(
            model_name="fightbatch",
            constraint=models.UniqueConstraint(fields=("run", "remote_index"), name="unique_fight_batch_per_run"),
        ),
        migrations.AddConstraint(
            model_name="fightstep",
            constraint=models.UniqueConstraint(fields=("fight", "step_number"), name="unique_step_per_imported_fight"),
        ),
    ]
