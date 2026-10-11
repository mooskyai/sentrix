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

from .models import AlertRule
from .serializers import AlertRuleSerializer, AlertRuleWriteSerializer
from .services import (
    AlertRuleAlreadyExists,
    AlertRuleLimitReached,
    create_alert_rule,
    update_alert_rule,
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
        raise PermissionDenied("Your role cannot manage alert rules.")
    return project


def _project_rule(project: Project, alert_rule_id: UUID) -> AlertRule:
    try:
        return AlertRule.objects.select_related("created_by").get(
            pk=alert_rule_id,
            project=project,
        )
    except AlertRule.DoesNotExist as exc:
        raise NotFound("Alert rule not found.") from exc


class AlertRuleListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID) -> Response:
        project = _readable_project(request, project_id)
        rules = AlertRule.objects.filter(project=project).select_related("created_by")
        return Response(AlertRuleSerializer(rules, many=True).data)

    def post(self, request: Request, project_id: UUID) -> Response:
        project = _writable_project(request, project_id)
        serializer = AlertRuleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rule = create_alert_rule(
                project=project,
                name=serializer.validated_data["name"],
                metric_name=serializer.validated_data["metric_name"],
                time_range=serializer.validated_data["time_range"],
                service_name=serializer.validated_data["service_name"],
                environment=serializer.validated_data["environment"],
                comparator=serializer.validated_data["comparator"],
                threshold=serializer.validated_data["threshold"],
                enabled=serializer.validated_data["enabled"],
                created_by=_authenticated_user(request),
            )
        except (AlertRuleAlreadyExists, AlertRuleLimitReached) as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(AlertRuleSerializer(rule).data, status=status.HTTP_201_CREATED)


class AlertRuleDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, project_id: UUID, alert_rule_id: UUID) -> Response:
        project = _readable_project(request, project_id)
        return Response(AlertRuleSerializer(_project_rule(project, alert_rule_id)).data)

    def patch(self, request: Request, project_id: UUID, alert_rule_id: UUID) -> Response:
        project = _writable_project(request, project_id)
        rule = _project_rule(project, alert_rule_id)
        serializer = AlertRuleWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        try:
            updated = update_alert_rule(
                rule=rule,
                name=values.get("name"),
                metric_name=values.get("metric_name"),
                time_range=values.get("time_range"),
                service_name=values.get("service_name"),
                environment=values.get("environment"),
                comparator=values.get("comparator"),
                threshold=values.get("threshold"),
                enabled=values.get("enabled"),
            )
        except AlertRuleAlreadyExists as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response(AlertRuleSerializer(updated).data)

    def delete(self, request: Request, project_id: UUID, alert_rule_id: UUID) -> Response:
        project = _writable_project(request, project_id)
        rule = _project_rule(project, alert_rule_id)
        rule.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
