from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.telemetry.logs_views import _optional_text
from apps.telemetry.metrics_views import _optional_dimension


def test_empty_environment_query_is_not_the_same_as_missing() -> None:
    factory = APIRequestFactory()
    absent = Request(factory.get("/"))
    empty = Request(factory.get("/?environment="))
    named = Request(factory.get("/?environment=acceptance"))
    assert _optional_text(absent, "environment", allow_empty=True) is None
    assert _optional_text(empty, "environment", allow_empty=True) == ""
    assert _optional_text(named, "environment", allow_empty=True) == "acceptance"
    assert _optional_dimension(absent, "environment", allow_empty=True) is None
    assert _optional_dimension(empty, "environment", allow_empty=True) == ""
    assert _optional_dimension(named, "environment", allow_empty=True) == "acceptance"


def test_other_optional_filters_keep_prior_empty_semantics() -> None:
    request = Request(APIRequestFactory().get("/?service_name=&body_contains="))
    assert _optional_text(request, "service_name") is None
    assert _optional_text(request, "body_contains") is None
    assert _optional_dimension(request, "service_name") is None
