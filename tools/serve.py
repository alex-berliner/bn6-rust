#!/usr/bin/env python3
"""Serve web/ on the LAN so the ROM can be played in a browser.

usage: python3 tools/serve.py [port]      (default 8123)

Static files only; web/index.html embeds EmulatorJS, which fetches its
WebAssembly mGBA core from its CDN, so the client needs internet for that
and this machine for the ROM. Responses are sent with no-cache headers so a
rebuilt ROM is picked up on reload. Rebuild the ROM with tools/web_rom.sh.
"""

import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8123
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"serving {os.path.abspath(WEB)} on http://0.0.0.0:{port}/", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
