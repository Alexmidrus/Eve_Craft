from __future__ import annotations

import html
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _OneShotCallbackServer(ThreadingHTTPServer):
    allow_reuse_address = True


class LocalOAuthCallbackListener:
    def __init__(self, callback_url: str) -> None:
        parsed = urllib.parse.urlparse(callback_url)
        if not parsed.scheme or not parsed.hostname or parsed.port is None:
            raise RuntimeError(f"Unsupported callback URL for local OAuth listener: {callback_url}")

        self._scheme = parsed.scheme
        self._host = parsed.hostname
        self._port = parsed.port
        self._path = parsed.path or "/"

    def wait_for_callback(self, timeout_seconds: int = 180) -> str:
        callback_received = threading.Event()
        callback_holder: dict[str, str] = {}
        expected_path = self._path
        scheme = self._scheme
        host = self._host

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
                parsed_path = urllib.parse.urlsplit(self.path)
                if parsed_path.path != expected_path:
                    self.send_error(404, "Unknown callback path.")
                    return

                callback_holder["callback_url"] = f"{scheme}://{host}:{self.server.server_address[1]}{self.path}"
                callback_received.set()
                self._write_html(
                    title="EVE SSO Completed",
                    body=(
                        "<h2>Authorization completed.</h2>"
                        "<p>You can return to Eve Craft and close this browser tab.</p>"
                    ),
                )
                threading.Thread(target=self.server.shutdown, daemon=True).start()

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

            def _write_html(self, *, title: str, body: str) -> None:
                page = (
                    "<html><head><meta charset='utf-8'/>"
                    f"<title>{html.escape(title)}</title>"
                    "</head><body>"
                    f"{body}"
                    "</body></html>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.end_headers()
                self.wfile.write(page)

        server = _OneShotCallbackServer((self._host, self._port), Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True)
        thread.start()

        try:
            if not callback_received.wait(timeout_seconds):
                raise TimeoutError("Timed out while waiting for the EVE SSO callback.")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        return callback_holder["callback_url"]

