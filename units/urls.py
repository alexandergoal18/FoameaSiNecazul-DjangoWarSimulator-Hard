from django.urls import path

from . import views

app_name = "units"

urlpatterns = [
    path("unit", views.create_unit, name="create"),
    path("unit/all", views.unit_list, name="all"),
    path("unit/<int:pk>", views.unit_detail, name="detail"),
    path("unit/<int:pk>/delete", views.delete_unit, name="delete"),
    path("unit/<int:pk>/heal/", views.heal_unit, name="heal"),
    path("fight/simulate/", views.start_fight, name="simulate"),
    path("fight/<int:pk>/", views.fight_detail, name="fight_detail"),
    path("unit/", views.create_unit),
    path("unit/all/", views.unit_list),
    path("unit/<int:pk>/", views.unit_detail),
]
