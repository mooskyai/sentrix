import math
from typing import Any

from rest_framework import serializers

from .models import AlertRule, AlertRuleState


class AlertRuleStateSerializer(serializers.ModelSerializer[AlertRuleState]):
    class Meta:
        model = AlertRuleState
        fields = (
            "status",
            "evaluated_at",
            "state_changed_at",
            "source_timestamp",
            "error_code",
            "updated_at",
        )
        read_only_fields = fields


class AlertRuleSerializer(serializers.ModelSerializer[AlertRule]):
    project_id = serializers.UUIDField(read_only=True)
    state = serializers.SerializerMethodField()

    class Meta:
        model = AlertRule
        fields = (
            "id",
            "project_id",
            "name",
            "metric_name",
            "time_range",
            "service_name",
            "environment",
            "comparator",
            "threshold",
            "enabled",
            "state",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_state(self, rule: AlertRule) -> dict[str, Any] | None:
        try:
            state = rule.evaluation_state
        except AlertRuleState.DoesNotExist:
            return None
        return dict(AlertRuleStateSerializer(state).data)


class AlertRuleWriteSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=160, trim_whitespace=True)
    metric_name = serializers.CharField(max_length=512, trim_whitespace=True)
    time_range = serializers.ChoiceField(
        choices=AlertRule.TimeRange.choices,
        default=AlertRule.TimeRange.ONE_HOUR,
    )
    service_name = serializers.CharField(
        max_length=512,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )
    environment = serializers.CharField(
        max_length=512,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )
    comparator = serializers.ChoiceField(choices=AlertRule.Comparator.choices)
    threshold = serializers.FloatField()
    enabled = serializers.BooleanField(default=True)

    def validate_threshold(self, value: float) -> float:
        if not math.isfinite(value):
            raise serializers.ValidationError("Threshold must be a finite number.")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if self.partial and not attrs:
            raise serializers.ValidationError("At least one alert-rule field is required.")
        return attrs
