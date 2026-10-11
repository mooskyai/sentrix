from collections import Counter
from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError

from apps.alerts.evaluation import evaluate_enabled_alert_rules
from apps.alerts.models import AlertRuleState


class Command(BaseCommand):
    help = "Evaluate enabled metric alert rules and persist their current state."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--project-id",
            type=UUID,
            default=None,
            help="Evaluate only enabled rules belonging to this project UUID.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        results = evaluate_enabled_alert_rules(project_id=options["project_id"])
        counts = Counter(result.status for result in results if not result.skipped)
        skipped = sum(1 for result in results if result.skipped)

        self.stdout.write(
            "Alert evaluation complete: "
            f"evaluated={len(results) - skipped}, skipped={skipped}, "
            f"ok={counts[AlertRuleState.Status.OK]}, "
            f"firing={counts[AlertRuleState.Status.FIRING]}, "
            f"no_data={counts[AlertRuleState.Status.NO_DATA]}, "
            f"error={counts[AlertRuleState.Status.ERROR]}."
        )

        errors = counts[AlertRuleState.Status.ERROR]
        if errors:
            raise CommandError(f"{errors} alert rule(s) ended in the error state.")
