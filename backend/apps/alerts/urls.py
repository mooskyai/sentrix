from django.urls import path

from .views import AlertRuleDetailView, AlertRuleListCreateView

urlpatterns = [
    path(
        "projects/<uuid:project_id>/alert-rules/",
        AlertRuleListCreateView.as_view(),
        name="project-alert-rule-list",
    ),
    path(
        "projects/<uuid:project_id>/alert-rules/<uuid:alert_rule_id>/",
        AlertRuleDetailView.as_view(),
        name="project-alert-rule-detail",
    ),
]
