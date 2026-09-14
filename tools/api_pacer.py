#!/usr/bin/env python3
"""A local pacing proxy in front of a provider's API, so a subscription's short-term rate limit is never seen
by the agents: pi talks to http://127.0.0.1:<port>/..., the pacer forwards to the upstream, spacing request
starts to at most `rpm` a minute (and at most `concurrency` in flight), streams the reply back, and on a 429
or 5xx waits (Retry-After, else doubling from 2 s) and retries up to `retries` times before passing the error
through. Per-request lines go to the log: time, path, status, seconds, retries.

  python3 tools/api_pacer.py --provider minimax --port 8791 --upstream https://api.minimax.io --rpm 20 --concurrency 2
  (tools/pacer.sh start|stop|status <provider> reads those numbers from providers.toml [providers.X.pacer])
"""
import argparse, http.server, socketserver, sys, threading, time, urllib.error, urllib.request

HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "host", "accept-encoding"}


class Pacer:
    def __init__(self, rpm, concurrency):
        self.gap = 60.0 / rpm if rpm > 0 else 0.0; self.lock = threading.Lock(); self.next_at = 0.0
        self.sem = threading.BoundedSemaphore(max(1, concurrency))

    def wait(self):
        with self.lock:
            now = time.time(); start = max(now, self.next_at); self.next_at = start + self.gap
        if start > time.time(): time.sleep(start - time.time())


def make_handler(a, pacer, log):
    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"      # a reply ends when the connection closes: streams pass through unbuffered

        def log_message(self, *x): pass

        def do_POST(self): self.forward()
        def do_GET(self): self.forward()

        def forward(self):
            n = int(self.headers.get("Content-Length") or 0); body = self.rfile.read(n) if n else None
            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
            url = a.upstream.rstrip("/") + self.path; t0 = time.time(); tries = 0
            with pacer.sem:
                while True:
                    pacer.wait(); tries += 1
                    req = urllib.request.Request(url, data=body, headers=headers, method=self.command)
                    try:
                        resp = urllib.request.urlopen(req, timeout=600); status = resp.status
                    except urllib.error.HTTPError as e:
                        status = e.code
                        if status in (429, 500, 502, 503, 504) and tries <= a.retries:
                            ra = e.headers.get("Retry-After"); delay = float(ra) if ra and ra.replace(".", "").isdigit() else min(60.0, 2.0 * 2 ** (tries - 1))
                            log("%s %s %d retry %d in %.0fs" % (time.strftime("%H:%M:%S"), self.path, status, tries, delay)); time.sleep(delay); continue
                        resp = e
                    except Exception as e:
                        log("%s %s upstream error %r" % (time.strftime("%H:%M:%S"), self.path, e)); self.send_error(502, "pacer: upstream error"); return
                    break
            self.send_response(status)
            for k, v in resp.headers.items():
                if k.lower() not in HOP: self.send_header(k, v)
            self.end_headers()
            try:
                while True:
                    chunk = resp.read(4096)
                    if not chunk: break
                    self.wfile.write(chunk); self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            log("%s %s %d %.1fs%s" % (time.strftime("%H:%M:%S"), self.path, status, time.time() - t0, (" after %d retries" % (tries - 1)) if tries > 1 else ""))
    return H


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True; allow_reuse_address = True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", required=True); ap.add_argument("--port", type=int, required=True); ap.add_argument("--upstream", required=True)
    ap.add_argument("--rpm", type=float, default=20); ap.add_argument("--concurrency", type=int, default=2); ap.add_argument("--retries", type=int, default=6)
    ap.add_argument("--log", default=None)
    a = ap.parse_args()
    out = open(a.log, "a") if a.log else sys.stderr
    def log(s): out.write(s + "\n"); out.flush()
    log("%s pacer for %s: %s -> %s, %.0f rpm, %d in flight, %d retries" % (time.strftime("%H:%M:%S"), a.provider, a.port, a.upstream, a.rpm, a.concurrency, a.retries))
    Server(("127.0.0.1", a.port), make_handler(a, Pacer(a.rpm, a.concurrency), log)).serve_forever()


if __name__ == "__main__":
    main()
