from django.urls import path

from .notification_views import (
    AlertNotificationDeliveryListView,
    NotificationChannelDetailView,
    NotificationChannelListCreateView,
)
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
    path(
        "projects/<uuid:project_id>/notification-channels/",
        NotificationChannelListCreateView.as_view(),
        name="project-notification-channel-list",
    ),
    path(
        "projects/<uuid:project_id>/notification-channels/<uuid:channel_id>/",
        NotificationChannelDetailView.as_view(),
        name="project-notification-channel-detail",
    ),
    path(
        "projects/<uuid:project_id>/notification-deliveries/",
        AlertNotificationDeliveryListView.as_view(),
        name="project-notification-delivery-list",
    ),
]
