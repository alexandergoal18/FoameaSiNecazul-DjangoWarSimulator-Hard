import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "war_simulator.settings")

app = Celery("war_simulator")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
