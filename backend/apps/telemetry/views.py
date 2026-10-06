from __future__ import annotations

import gzip
import json
import logging
from io import BytesIO

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.http import HttpRequest, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from google.rpc.status_pb2 import Status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from apps.projects.authentication import ProjectApiKeyAuthentication, ProjectApiKeyPrincipal
from apps.projects.services import TELEMETRY_WRITE_SCOPE

from .protocol import (
    OTLP_PROTOBUF_CONTENT_TYPE,
    OtlpDecodeError,
    OtlpSignal,
    decode_otlp_request,
    has_telemetry_records,
    success_response_payload,
)
from .sink import OtlpBatch, TelemetrySinkUnavailable, submit_otlp_batch

logger = logging.getLogger(__name__)


class OtlpPayloadTooLarge(ValueError):
    pass


class OtlpUnsupportedContentEncoding(ValueError):
    pass


class OtlpMalformedBody(ValueError):
    pass


def _status_response(
    *,
    request: HttpRequest,
    status_code: int,
    message: str,
) -> HttpResponse:
    status_message = Status(message=message)
    if request.content_type == OTLP_PROTOBUF_CONTENT_TYPE:
        payload = status_message.SerializeToString()
        content_type = OTLP_PROTOBUF_CONTENT_TYPE
    else:
        payload = json.dumps({"message": message}, separators=(",", ":")).encode("utf-8")
        content_type = "application/json"
    return HttpResponse(payload, status=status_code, content_type=content_type)


def _read_request_payload(request: HttpRequest) -> bytes:
    max_bytes = settings.OTLP_MAX_REQUEST_BYTES
    raw_content_length = request.META.get("CONTENT_LENGTH")
    if raw_content_length:
        try:
            content_length = int(raw_content_length)
        except ValueError as exc:
            raise OtlpMalformedBody("Invalid Content-Length header.") from exc
        if content_length > max_bytes:
            raise OtlpPayloadTooLarge

    try:
        raw_payload = request.body
    except RequestDataTooBig as exc:
        raise OtlpPayloadTooLarge from exc

    if len(raw_payload) > max_bytes:
        raise OtlpPayloadTooLarge

    content_encoding = request.headers.get("Content-Encoding", "").strip().lower()
    if content_encoding in {"", "identity"}:
        return raw_payload
    if content_encoding != "gzip":
        raise OtlpUnsupportedContentEncoding(content_encoding)

    try:
        with gzip.GzipFile(fileobj=BytesIO(raw_payload), mode="rb") as compressed:
            payload = compressed.read(max_bytes + 1)
    except (EOFError, OSError) as exc:
        raise OtlpMalformedBody("The gzip request body is invalid.") from exc

    if len(payload) > max_bytes:
        raise OtlpPayloadTooLarge
    return payload


def _authenticate_machine(request: HttpRequest) -> ProjectApiKeyPrincipal | HttpResponse:
    try:
        authentication = ProjectApiKeyAuthentication().authenticate(Request(request))
    except AuthenticationFailed:
        return _status_response(
            request=request,
            status_code=401,
            message="Invalid project API key.",
        )

    if authentication is None:
        return _status_response(
            request=request,
            status_code=401,
            message="Project API key authentication is required.",
        )

    principal, _api_key = authentication
    if TELEMETRY_WRITE_SCOPE not in principal.scopes:
        return _status_response(
            request=request,
            status_code=403,
            message="The project API key lacks telemetry:write scope.",
        )
    return principal


@method_decorator(csrf_exempt, name="dispatch")
class OtlpHttpView(View):
    signal: OtlpSignal

    def post(self, request: HttpRequest) -> HttpResponse:
        principal_or_response = _authenticate_machine(request)
        if isinstance(principal_or_response, HttpResponse):
            return principal_or_response
        principal = principal_or_response

        if request.content_type != OTLP_PROTOBUF_CONTENT_TYPE:
            return _status_response(
                request=request,
                status_code=415,
                message="M2.3 accepts OTLP/HTTP binary protobuf only.",
            )

        try:
            payload = _read_request_payload(request)
        except OtlpPayloadTooLarge:
            return _status_response(
                request=request,
                status_code=413,
                message="OTLP request body exceeds the configured limit.",
            )
        except OtlpUnsupportedContentEncoding:
            return _status_response(
                request=request,
                status_code=415,
                message="Unsupported OTLP content encoding.",
            )
        except OtlpMalformedBody as exc:
            return _status_response(request=request, status_code=400, message=str(exc))

        try:
            message = decode_otlp_request(signal=self.signal, payload=payload)
        except OtlpDecodeError as exc:
            return _status_response(request=request, status_code=400, message=str(exc))

        if has_telemetry_records(signal=self.signal, message=message):
            batch = OtlpBatch(
                organization_id=principal.organization_id,
                project_id=principal.project_id,
                api_key_id=principal.api_key_id,
                signal=self.signal,
                message=message,
            )
            try:
                submit_otlp_batch(batch)
            except TelemetrySinkUnavailable:
                return _status_response(
                    request=request,
                    status_code=503,
                    message="Telemetry persistence is not available yet.",
                )
            except Exception:
                logger.exception(
                    "Unexpected OTLP sink failure",
                    extra={
                        "organization_id": str(principal.organization_id),
                        "project_id": str(principal.project_id),
                        "api_key_id": str(principal.api_key_id),
                        "signal": self.signal.value,
                    },
                )
                return _status_response(
                    request=request,
                    status_code=500,
                    message="Telemetry processing failed.",
                )

        return HttpResponse(
            success_response_payload(self.signal),
            status=200,
            content_type=OTLP_PROTOBUF_CONTENT_TYPE,
        )


class OtlpMetricsView(OtlpHttpView):
    signal = OtlpSignal.METRICS


class OtlpLogsView(OtlpHttpView):
    signal = OtlpSignal.LOGS


class OtlpTracesView(OtlpHttpView):
    signal = OtlpSignal.TRACES
