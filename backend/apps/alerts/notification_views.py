from __future__ import annotations

from uuid import UUID

from django.contrib.auth.models import User
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.organizations.selectors import WRITE_ROLES, membership_for_user
from apps.projects.models import Project
from apps.projects.selectors import projects_for_user

from .models import AlertNotificationDelivery, NotificationChannel
from .notification_channels import (
    NotificationChannelAlreadyExists,
    NotificationChannelLimitReached,
    create_notification_channel,
    derive_webhook_signing_secret,
    update_notification_channel,
)
from .notification_serializers import (
    AlertNotificationDeliverySerializer,
    NotificationChannelSerializer,
    NotificationChannelWriteSerializer,
)


def _authenticated_user(request: Request) -> User:
    user = request.user
    if not isinstance(user, User):
        raise PermissionDenied("Authentication is required.")
    return user


def _readable_project(request: Request, project_id: UUID) -> Project:
    user = _authenticated_user(request)
    try:
        return projects_for_user(user).select_related("organization").get(pk=project_id)
    except Project.DoesNotExist as exc:
        raise NotFound("Project not found.") from exc


def _writable_project(request: Request, project_id: UUID) -> Project:
    project = _readable_project(request, project_id)
    membership = membership_for_user(
        user=_authenticated_user(request),
        organization=project.organization,
    )
    if membership is None or membership.role not in WRITE_ROLES:
        raise PermissionDenied("Your role cannot manage notification channels.")
    return project


def _project_channel(project: Project, channel_id: UUID) -> NotificationChannel:
    try:
        return NotificationChannel.objects.get(pk=channel_id, project=project)
    except NotificationChannel.DoesNotExist as exc:
        raise NotFound("Notification channel not found.") from exc


class NotificationChannelListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID) -> Response:
        project = _readable_project(request, project_id)
        channels = NotificationChannel.objects.filter(project=project).select_related("created_by")
        return Response(NotificationChannelSerializer(channels, many=True).data)

    def post(self, request: Request, project_id: UUID) -> Response:
        project = _writable_project(request, project_id)
        serializer = NotificationChannelWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            channel = create_notification_channel(
                project=project,
                name=serializer.validated_data["name"],
                endpoint_url=serializer.validated_data["endpoint_url"],
                enabled=serializer.validated_data["enabled"],
                created_by=_authenticated_user(request),
            )
        except (NotificationChannelAlreadyExists, NotificationChannelLimitReached) as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        data = dict(NotificationChannelSerializer(channel).data)
        data["signing_secret"] = derive_webhook_signing_secret(channel.id)
        return Response(data, status=status.HTTP_201_CREATED)


class NotificationChannelDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID, channel_id: UUID) -> Response:
        project = _readable_project(request, project_id)
        return Response(NotificationChannelSerializer(_project_channel(project, channel_id)).data)

    def patch(self, request: Request, project_id: UUID, channel_id: UUID) -> Response:
        project = _writable_project(request, project_id)
        channel = _project_channel(project, channel_id)
        serializer = NotificationChannelWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            updated = update_notification_channel(
                channel=channel,
                name=values.get("name"),
                endpoint_url=values.get("endpoint_url"),
                enabled=values.get("enabled"),
            )
        except NotificationChannelAlreadyExists as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(NotificationChannelSerializer(updated).data)

    def delete(self, request: Request, project_id: UUID, channel_id: UUID) -> Response:
        project = _writable_project(request, project_id)
        channel = _project_channel(project, channel_id)
        channel.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AlertNotificationDeliveryListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID) -> Response:
        project = _readable_project(request, project_id)
        raw_limit = request.query_params.get("limit", "100")
        try:
            limit = int(raw_limit)
        except ValueError as exc:
            raise ValidationError({"limit": "Limit must be an integer."}) from exc
        if not 1 <= limit <= 500:
            raise ValidationError({"limit": "Limit must be between 1 and 500."})
        deliveries = (
            AlertNotificationDelivery.objects.filter(channel__project=project)
            .select_related("channel")
            .order_by("-created_at", "-id")[:limit]
        )
        return Response(AlertNotificationDeliverySerializer(deliveries, many=True).data)
