from django.urls import path

from . import views

app_name = "hardchallenge"

urlpatterns = [
    path("hard", views.dashboard, name="dashboard"),
    path("hard/import", views.start_import, name="start_import"),
    path("hard/people", views.people, name="people"),
    path("hard/fights", views.fights, name="fights"),
    path("hard/fights/<int:pk>", views.fight_detail, name="fight_detail"),
    path("simulate", views.simulate, name="simulate"),
    path("simulate/start", views.start_simulation, name="start_simulation"),
    path("hard/", views.dashboard),
    path("hard/people/", views.people),
    path("hard/fights/", views.fights),
    path("simulate/", views.simulate),
]
