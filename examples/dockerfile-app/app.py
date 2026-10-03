import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", 8080))


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {
                "status": "healthy",
                "app": "dockerfile-sample-app",
                "port": PORT,
                "message": "Hello from custom user-supplied Dockerfile!",
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "not found"}).encode("utf-8"))

    def log_message(self, format, *args):
        sys.stdout.write(f"[dockerfile-app] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()


def run():
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, AppHandler)
    print(f"[dockerfile-app] Server started at http://0.0.0.0:{PORT}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    run()
