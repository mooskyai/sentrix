from django.core.management.base import BaseCommand, CommandError

from apps.telemetry.clickhouse_schema import (
    TELEMETRY_TABLE_SCHEMAS,
    ensure_clickhouse_schema,
    get_clickhouse_client,
    validate_clickhouse_schema,
)


class Command(BaseCommand):
    help = "Create or validate the Sentrix ClickHouse telemetry schema."

    def add_arguments(self, parser) -> None:  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--check",
            action="store_true",
            help="Validate the existing ClickHouse schema without creating tables.",
        )

    def handle(self, *args, **options) -> None:  # type: ignore[no-untyped-def]
        del args
        client = get_clickhouse_client()
        try:
            if not options["check"]:
                ensure_clickhouse_schema(client)

            errors = validate_clickhouse_schema(client)
            if errors:
                raise CommandError("\n".join(errors))

            action = "Validated" if options["check"] else "Applied and validated"
            tables = ", ".join(schema.name for schema in TELEMETRY_TABLE_SCHEMAS)
            self.stdout.write(self.style.SUCCESS(f"{action} ClickHouse schema: {tables}"))
        finally:
            client.close()
