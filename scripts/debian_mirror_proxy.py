"""Small allow-listed HTTP proxy for a slow deb.debian.org course host.

The proxy rewrites only deb.debian.org requests to a configured Debian mirror.
It is an environment workaround: candidate Dockerfiles remain byte-identical.
"""

import argparse
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
from urllib.parse import urlsplit


class DebianMirrorProxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    mirror_host = "mirrors.aliyun.com"
    timeout_seconds = 120

    def _forward(self, *, send_body: bool) -> None:
        parsed = urlsplit(self.path)
        host = parsed.hostname or self.headers.get("Host", "").split(":", 1)[0]
        if parsed.scheme not in {"", "http"} or host != "deb.debian.org":
            self.send_error(403, "only http://deb.debian.org is allowed")
            return
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        connection = HTTPConnection(self.mirror_host, 80, timeout=self.timeout_seconds)
        try:
            connection.request(
                self.command,
                path,
                headers={
                    "Host": self.mirror_host,
                    "User-Agent": self.headers.get("User-Agent", "apt"),
                    "Accept": self.headers.get("Accept", "*/*"),
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            self.send_response(response.status, response.reason)
            for name, value in response.getheaders():
                if name.lower() not in {
                    "connection",
                    "keep-alive",
                    "proxy-authenticate",
                    "proxy-authorization",
                    "te",
                    "trailers",
                    "transfer-encoding",
                    "upgrade",
                }:
                    self.send_header(name, value)
            self.send_header("Connection", "close")
            self.end_headers()
            if send_body:
                while chunk := response.read(64 * 1024):
                    self.wfile.write(chunk)
        except (OSError, TimeoutError) as exc:
            self.send_error(502, f"mirror request failed: {exc}")
        finally:
            connection.close()
            self.close_connection = True

    def do_GET(self) -> None:
        self._forward(send_body=True)

    def do_HEAD(self) -> None:
        self._forward(send_body=False)

    def log_message(self, message, *args) -> None:
        print(f"{self.address_string()} {message % args}", file=sys.stderr, flush=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--listen", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3142)
    parser.add_argument("--mirror", default="mirrors.aliyun.com")
    args = parser.parse_args(argv)
    DebianMirrorProxy.mirror_host = args.mirror
    server = ThreadingHTTPServer((args.listen, args.port), DebianMirrorProxy)
    print(
        f"proxy=http://{args.listen}:{args.port} mirror=http://{args.mirror}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
