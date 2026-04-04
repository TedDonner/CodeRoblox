from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .models import Operation, OperationOutcome, ProjectSnapshot
from .service import AgentError, AgentService, BatchNotFoundError, SessionNotFoundError


class JsonHttpServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], service: AgentService) -> None:
        super().__init__(server_address, build_handler())
        self.service = service


def build_handler() -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server: JsonHttpServer

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)

            if parsed.path == "/health":
                self._write_json(HTTPStatus.OK, self.server.service.health())
                return

            if parsed.path == "/api/operations/next":
                session_id = self._require_query_value(query, "session_id")
                self._handle(
                    lambda: self.server.service.next_batch(session_id),
                    HTTPStatus.OK,
                )
                return

            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            body = self._read_json_body()

            routes: dict[str, tuple[int, Any]] = {
                "/api/sessions": (
                    HTTPStatus.CREATED,
                    lambda: self.server.service.start_session(
                        client_name=str(body.get("client_name", "roblox-studio-plugin")),
                        project_root=str(body.get("project_root", "")),
                        capabilities=dict(body.get("capabilities", {})),
                    ),
                ),
                "/api/snapshots": (
                    HTTPStatus.ACCEPTED,
                    lambda: self.server.service.store_snapshot(
                        session_id=str(body["session_id"]),
                        snapshot=ProjectSnapshot.from_dict(dict(body["snapshot"])),
                    ),
                ),
                "/api/operations/validate": (
                    HTTPStatus.OK,
                    lambda: self.server.service.validate_operations(
                        session_id=str(body["session_id"]),
                        operations=[Operation.from_dict(item) for item in body.get("operations", [])],
                        allow_destructive=bool(body.get("allow_destructive", False)),
                    ),
                ),
                "/api/operations/queue": (
                    HTTPStatus.ACCEPTED,
                    lambda: self.server.service.queue_operations(
                        session_id=str(body["session_id"]),
                        operations=[Operation.from_dict(item) for item in body.get("operations", [])],
                        allow_destructive=bool(body.get("allow_destructive", False)),
                    ),
                ),
                "/api/operations/result": (
                    HTTPStatus.OK,
                    lambda: self.server.service.complete_batch(
                        session_id=str(body["session_id"]),
                        batch_id=str(body["batch_id"]),
                        outcomes=[
                            OperationOutcome.from_dict(item) for item in body.get("outcomes", [])
                        ],
                    ),
                ),
                "/api/checkpoints": (
                    HTTPStatus.CREATED,
                    lambda: {
                        "checkpoint": self.server.service.create_checkpoint(
                            session_id=str(body["session_id"]),
                            label=str(body.get("label", "manual-checkpoint")),
                        ).to_dict()
                    },
                ),
                "/api/rollback": (
                    HTTPStatus.ACCEPTED,
                    lambda: self.server.service.queue_rollback(
                        session_id=str(body["session_id"]),
                        checkpoint_id=str(body["checkpoint_id"]),
                    ),
                ),
            }

            route = routes.get(parsed.path)
            if route is None:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "Route not found."})
                return

            status_code, callback = route
            self._handle(callback, status_code)

        def _handle(self, callback: Any, success_status: HTTPStatus) -> None:
            try:
                payload = callback()
            except KeyError as exc:
                self._write_json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": f"Missing required field: {exc.args[0]}"},
                )
                return
            except SessionNotFoundError as exc:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            except BatchNotFoundError as exc:
                self._write_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
                return
            except AgentError as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            except json.JSONDecodeError:
                self._write_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON body."})
                return

            self._write_json(success_status, payload)

        def _read_json_body(self) -> dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length == 0:
                return {}

            raw = self.rfile.read(content_length)
            return json.loads(raw.decode("utf-8"))

        def _require_query_value(
            self, query: dict[str, list[str]], key: str, default: str | None = None
        ) -> str:
            values = query.get(key)
            if values and values[0]:
                return values[0]
            if default is not None:
                return default
            raise AgentError(f"Missing query parameter: {key}")

        def _write_json(self, status_code: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(int(status_code))
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the CodeRoblox local orchestration agent.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind to.")
    parser.add_argument("--port", default=8787, type=int, help="Port to listen on.")
    args = parser.parse_args(argv)

    service = AgentService()
    server = JsonHttpServer((args.host, args.port), service)
    print(f"CodeRoblox agent listening on http://{args.host}:{args.port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
