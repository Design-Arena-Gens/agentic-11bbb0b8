import json
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any, Dict

from jarvis import JarvisAssistant


assistant = JarvisAssistant()


def _json_dump(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload).encode("utf-8")


class handler(BaseHTTPRequestHandler):
    """Vercel-compatible HTTP handler for the Jarvis assistant."""

    protocol_version = "HTTP/1.1"

    def _set_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def _send(
        self,
        status: HTTPStatus,
        payload: Dict[str, Any],
    ) -> None:
        body = _json_dump(payload)
        self.send_response(status.value)
        self._set_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self._set_cors()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length) if content_length else b"{}"
            data = json.loads(raw_body.decode("utf-8"))
            message = data.get("message")
            history = data.get("history", [])
            if not isinstance(history, list):
                history = []
            if not message:
                self._send(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "Missing 'message' in payload."},
                )
                return
            result = assistant.handle(str(message), history)
            self._send(HTTPStatus.OK, result)
        except json.JSONDecodeError:
            self._send(
                HTTPStatus.BAD_REQUEST,
                {"error": "Invalid JSON payload."},
            )
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._send(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "Assistant processing failure.", "detail": str(exc)},
            )

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return
