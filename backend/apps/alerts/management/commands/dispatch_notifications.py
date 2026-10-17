from collections import Counter
from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.alerts.models import AlertNotificationDelivery
from apps.alerts.notifications import dispatch_due_notifications


class Command(BaseCommand):
    help = "Dispatch due alert notification deliveries through configured project webhooks."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--project-id", type=UUID, default=None)
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            results = dispatch_due_notifications(
                project_id=options["project_id"],
                limit=options["limit"],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        counts = Counter(result.status for result in results)
        skipped = sum(1 for result in results if result.skipped)
        self.stdout.write(
            "Notification dispatch complete: "
            f"processed={len(results)}, "
            f"delivered={counts[AlertNotificationDelivery.Status.DELIVERED]}, "
            f"retry={counts[AlertNotificationDelivery.Status.RETRY]}, "
            f"failed={counts[AlertNotificationDelivery.Status.FAILED]}, "
            f"cancelled={counts[AlertNotificationDelivery.Status.CANCELLED]}, "
            f"skipped={skipped}."
        )
        if counts[AlertNotificationDelivery.Status.FAILED]:
            raise CommandError(
                f"{counts[AlertNotificationDelivery.Status.FAILED]} notification delivery "
                "record(s) "
                "reached terminal failure."
            )
