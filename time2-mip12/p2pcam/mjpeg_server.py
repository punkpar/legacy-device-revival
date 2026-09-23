import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

    daemon_threads = True


class MJPEGServer:
    """A class to stream bytes frames to a HTTP MJPEG server."""

    def __init__(self, port: int = 8080) -> None:
        """Initialize a HTTP MJPEG server on localhost:8080 by default."""
        self.port = port
        self.latest_frame = None
        self.frame_condition = threading.Condition()
        self.server = None
        self.server_thread = None

    def update_frame(self, frame: bytes) -> None:
        """Update the current frame and notify all connected clients."""
        with self.frame_condition:
            self.latest_frame = frame
            self.frame_condition.notify_all()

    def start(self) -> None:
        """Start the HTTP server in a background thread."""
        server_instance = self

        class StreamingHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):  # noqa: A002, ANN002
                # Suppress default HTTP logging to avoid spamming the console
                pass

            def do_GET(self):
                if self.path == "/stream":
                    self.send_response(200)
                    self.send_header(
                        "Content-type",
                        "multipart/x-mixed-replace; boundary=--jpgboundary",
                    )
                    self.end_headers()

                    while True:
                        try:
                            with server_instance.frame_condition:
                                # Wait for a new frame to be available
                                server_instance.frame_condition.wait(timeout=1.0)
                                frame = server_instance.latest_frame

                            if frame is None:
                                continue

                            self.wfile.write(b"--jpgboundary\r\n")
                            self.send_header("Content-type", "image/jpeg")
                            self.send_header("Content-length", str(len(frame)))
                            self.end_headers()
                            self.wfile.write(frame)
                            self.wfile.write(b"\r\n")
                        except Exception:  # noqa: BLE001
                            # Client disconnected (e.g. Broken pipe)
                            break
                else:
                    self.send_response(404)
                    self.end_headers()

        self.server = ThreadedHTTPServer(("", self.port), StreamingHandler)
        self.server_thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.server_thread.start()
        print(f"MJPEG server started at http://localhost:{self.port}/stream")

    def stop(self) -> None:
        """Stop the HTTP server cleanly."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
