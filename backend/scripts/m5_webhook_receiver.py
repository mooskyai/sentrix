from __future__ import annotations

import argparse
import base64
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar


class _ReceiverHandler(BaseHTTPRequestHandler):
    output_path: ClassVar[Path]
    expected_path: ClassVar[str]
    max_requests: ClassVar[int]
    requests_seen: ClassVar[int] = 0

    def do_POST(self) -> None:
        if self.path != self.expected_path:
            self.send_response(404)
            self.end_headers()
            return

        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError:
            self.send_response(400)
            self.end_headers()
            return
        body = self.rfile.read(length)
        record = {
            "path": self.path,
            "headers": {key: value for key, value in self.headers.items()},
            "body_b64": base64.b64encode(body).decode("ascii"),
        }
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")

        self.send_response(204)
        self.end_headers()
        type(self).requests_seen += 1
        if type(self).requests_seen >= self.max_requests:
            self.server.shutdown()

    def log_message(self, format: str, *args: object) -> None:
        return


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Disposable M5 webhook receiver.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--path", default="/sentrix")
    parser.add_argument("--output", required=True)
    parser.add_argument("--ready-file", required=True)
    parser.add_argument("--max-requests", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not 1 <= int(args.port) <= 65535:
        raise SystemExit("Port must be between 1 and 65535.")
    if int(args.max_requests) < 1:
        raise SystemExit("max-requests must be at least 1.")

    output_path = Path(str(args.output))
    ready_path = Path(str(args.ready_file))
    output_path.unlink(missing_ok=True)
    ready_path.unlink(missing_ok=True)

    _ReceiverHandler.output_path = output_path
    _ReceiverHandler.expected_path = str(args.path)
    _ReceiverHandler.max_requests = int(args.max_requests)
    _ReceiverHandler.requests_seen = 0

    server = ThreadingHTTPServer((str(args.host), int(args.port)), _ReceiverHandler)
    ready_path.write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "host": str(args.host),
                "port": int(args.port),
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
