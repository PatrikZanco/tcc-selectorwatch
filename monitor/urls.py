from django.urls import path

from . import views

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("events/", views.EventListView.as_view(), name="event_list"),
    path("events/<int:pk>/", views.EventDetailView.as_view(), name="event_detail"),
    path("history/", views.HistoryView.as_view(), name="history"),

    # Sites
    path("sites/", views.SiteListView.as_view(), name="site_list"),
    path("sites/<int:pk>/", views.SiteDetailView.as_view(), name="site_detail"),
    path("sites/<int:pk>/delete/", views.SiteDeleteView.as_view(), name="site_delete"),

    # Seletores
    path("sites/<int:site_pk>/selectors/add/", views.SelectorCreateView.as_view(), name="selector_create"),
    path("selectors/<int:pk>/edit/", views.SelectorEditView.as_view(), name="selector_edit"),
    path("selectors/<int:pk>/delete/", views.SelectorDeleteView.as_view(), name="selector_delete"),
]
