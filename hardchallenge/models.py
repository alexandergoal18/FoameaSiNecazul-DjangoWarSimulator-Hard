from django.core.validators import MinValueValidator
from django.db import models


class Person(models.Model):
    """A remote person who becomes a soldier after a draft batch is applied."""

    external_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=255)
    age = models.PositiveSmallIntegerField()
    rank = models.CharField(max_length=100, null=True, blank=True)
    health = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(0)])
    drafted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["external_id"]

    def __str__(self):
        return f"{self.name} ({self.external_id})"


class ChallengeRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED)
    people_count = models.PositiveIntegerField(default=0)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class BatchStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    DOWNLOADING = "downloading", "Downloading"
    DOWNLOADED = "downloaded", "Downloaded"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class DraftBatch(models.Model):
    run = models.ForeignKey(ChallengeRun, on_delete=models.CASCADE, related_name="draft_batches")
    remote_index = models.PositiveIntegerField()
    next_batch = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=BatchStatus.choices, default=BatchStatus.QUEUED)
    person_count = models.PositiveIntegerField(default=0)
    error_detail = models.TextField(blank=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "remote_index"], name="unique_draft_batch_per_run")]
        ordering = ["remote_index"]


class FightBatch(models.Model):
    run = models.ForeignKey(ChallengeRun, on_delete=models.CASCADE, related_name="fight_batches")
    remote_index = models.PositiveIntegerField()
    next_batch = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=BatchStatus.choices, default=BatchStatus.QUEUED)
    fight_count = models.PositiveIntegerField(default=0)
    error_detail = models.TextField(blank=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["run", "remote_index"], name="unique_fight_batch_per_run")]
        ordering = ["remote_index"]


class ImportedFight(models.Model):
    class ImportStatus(models.TextChoices):
        QUEUED = "queued", "Queued"
        IMPORTING = "importing", "Importing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class ReplayStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    remote_fight_id = models.PositiveIntegerField(unique=True)
    batch = models.ForeignKey(FightBatch, null=True, blank=True, on_delete=models.SET_NULL, related_name="fights")
    blue_soldier = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="blue_fights")
    red_soldier = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="red_fights")
    import_status = models.CharField(max_length=16, choices=ImportStatus.choices, default=ImportStatus.QUEUED)
    replay_status = models.CharField(max_length=16, choices=ReplayStatus.choices, default=ReplayStatus.PENDING)
    error_detail = models.TextField(blank=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    replayed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["remote_fight_id"]


class FightStep(models.Model):
    fight = models.ForeignKey(ImportedFight, on_delete=models.CASCADE, related_name="steps")
    step_number = models.PositiveIntegerField()
    attacker = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="attacks")
    defender = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="defences")
    damage = models.PositiveSmallIntegerField(validators=[MinValueValidator(0)])
    defender_health_after = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["fight", "step_number"], name="unique_step_per_imported_fight")]
        ordering = ["step_number"]
