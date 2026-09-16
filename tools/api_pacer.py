#!/usr/bin/env python3
"""A local pacing proxy in front of a provider's API, so a subscription's short-term rate limit is never seen
by the agents: pi talks to http://127.0.0.1:<port>/..., the pacer forwards to the upstream, spacing request
starts to at most `rpm` a minute (and at most `concurrency` in flight), streams the reply back, and on a 429
or 5xx waits (Retry-After, else doubling from 2 s) and retries up to `retries` times before passing the error
through. Per-request lines go to the log: time, path, status, seconds, retries.

  python3 tools/api_pacer.py --provider minimax --port 8791 --upstream https://api.minimax.io --rpm 20 --concurrency 2
  (tools/pacer.sh start|stop|status <provider> reads those numbers from providers.toml [providers.X.pacer])
"""
import argparse, http.server, json, socketserver, sys, threading, time, urllib.error, urllib.request

HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "host", "accept-encoding"}


# ---------------------------------------------------------------- OpenAI Responses translation
# Some models on a gateway are served only by the Responses API (OpenCode Go's gpt-5.6-luna,
# muse-spark-1.3-contributor and grok-4.6 answer 500 or "not supported for format oa-compat" on
# /v1/chat/completions, 2026-09-16). pi speaks chat-completions, so the pacer translates for exactly
# the models named with --responses-model: the request is rewritten, the upstream call is made without
# streaming, and the reply is turned back into a chat completion (or into one short stream of chunks
# when the caller asked to stream).

REASONING_HEADROOM = 4096


def _text_of(content):
    if content is None: return ""
    if isinstance(content, str): return content
    out = []
    for c in content:
        if isinstance(c, str): out.append(c)
        elif isinstance(c, dict) and c.get("type") in ("text", "input_text", "output_text"): out.append(c.get("text", ""))
    return "".join(out)


def to_responses(body):
    """a chat-completions request as a Responses request"""
    out = {"model": body["model"]}
    inp, instructions = [], []
    for m in body.get("messages", []):
        role, content = m.get("role"), m.get("content")
        if role in ("system", "developer"):
            instructions.append(_text_of(content)); continue
        if role == "tool":
            inp.append({"type": "function_call_output", "call_id": m.get("tool_call_id"), "output": _text_of(content)}); continue
        if role == "assistant":
            t = _text_of(content)
            if t: inp.append({"role": "assistant", "content": [{"type": "output_text", "text": t}]})
            for c in m.get("tool_calls") or []:
                f = c.get("function") or {}
                inp.append({"type": "function_call", "call_id": c.get("id"), "name": f.get("name"), "arguments": f.get("arguments") or "{}"})
            continue
        inp.append({"role": "user", "content": [{"type": "input_text", "text": _text_of(content)}]})
    out["input"] = inp
    if instructions: out["instructions"] = "\n\n".join(x for x in instructions if x)
    n = body.get("max_completion_tokens") or body.get("max_tokens")
    # a Responses model counts its hidden reasoning against this budget (muse-spark spent 252 tokens thinking
    # before its first word, 2026-09-16), so the caller's ceiling on VISIBLE output gets that headroom added
    if n: out["max_output_tokens"] = n + REASONING_HEADROOM
    for k in ("temperature", "top_p"):
        if k in body: out[k] = body[k]
    tools = []
    for t in body.get("tools") or []:
        f = t.get("function") or {}
        tools.append({"type": "function", "name": f.get("name"), "description": f.get("description"), "parameters": f.get("parameters")})
    if tools: out["tools"] = tools
    tc = body.get("tool_choice")
    if isinstance(tc, str) and tc in ("auto", "none", "required"): out["tool_choice"] = tc
    elif isinstance(tc, dict): out["tool_choice"] = {"type": "function", "name": (tc.get("function") or {}).get("name")}
    out["stream"] = False
    return out


def from_responses(r, model):
    """a Responses reply as a chat completion"""
    text, calls = [], []
    for item in r.get("output") or []:
        kind = item.get("type")
        if kind == "message":
            for c in item.get("content") or []:
                if c.get("type") in ("output_text", "text"): text.append(c.get("text", ""))
        elif kind == "function_call":
            calls.append({"id": item.get("call_id") or item.get("id"), "type": "function",
                          "function": {"name": item.get("name"), "arguments": item.get("arguments") or "{}"}})
    msg = {"role": "assistant", "content": "".join(text) or None}
    if calls: msg["tool_calls"] = calls
    finish = "tool_calls" if calls else ("length" if r.get("status") == "incomplete" else "stop")
    u = r.get("usage") or {}
    ptok, ctok = u.get("input_tokens", 0), u.get("output_tokens", 0)
    return {"id": r.get("id", "chatcmpl-translated"), "object": "chat.completion", "model": model,
            "created": int(r.get("created_at") or time.time()),
            "choices": [{"index": 0, "message": msg, "finish_reason": finish, "logprobs": None}],
            "usage": {"prompt_tokens": ptok, "completion_tokens": ctok, "total_tokens": u.get("total_tokens", ptok + ctok),
                      "prompt_tokens_details": {"cached_tokens": (u.get("input_tokens_details") or {}).get("cached_tokens", 0)},
                      "completion_tokens_details": {"reasoning_tokens": (u.get("output_tokens_details") or {}).get("reasoning_tokens", 0)}}}


def as_stream(cc):
    """a finished chat completion as the SSE chunks a streaming caller expects"""
    base = {"id": cc["id"], "object": "chat.completion.chunk", "created": cc["created"], "model": cc["model"]}
    ch = cc["choices"][0]; msg = ch["message"]; out = []
    def chunk(delta, finish=None):
        d = dict(base); d["choices"] = [{"index": 0, "delta": delta, "finish_reason": finish}]
        return "data: " + json.dumps(d) + "\n\n"
    out.append(chunk({"role": "assistant", "content": ""}))
    if msg.get("content"): out.append(chunk({"content": msg["content"]}))
    for i, c in enumerate(msg.get("tool_calls") or []):
        out.append(chunk({"tool_calls": [{"index": i, "id": c["id"], "type": "function", "function": c["function"]}]}))
    last = dict(base); last["choices"] = [{"index": 0, "delta": {}, "finish_reason": ch["finish_reason"]}]; last["usage"] = cc["usage"]
    out.append("data: " + json.dumps(last) + "\n\n"); out.append("data: [DONE]\n\n")
    return "".join(out).encode()


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
            for h in a.header:
                k, _, v = h.partition(":"); headers[k.strip()] = v.strip()
            path = self.path; translate = False; want_stream = False; model = ""
            if a.responses_model and path.endswith("/chat/completions") and body:
                try: req = json.loads(body)
                except ValueError: req = None
                if isinstance(req, dict) and req.get("model") in a.responses_model:
                    translate = True; want_stream = bool(req.get("stream")); model = req["model"]
                    body = json.dumps(to_responses(req)).encode()
                    path = path[: -len("/chat/completions")] + "/responses"
                    headers["Content-Length"] = str(len(body))
            url = a.upstream.rstrip("/") + path; t0 = time.time(); tries = 0
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
            if translate and status == 200:
                try:
                    cc = from_responses(json.loads(resp.read().decode()), model)
                except Exception as e:
                    log("%s %s translate failed: %r" % (time.strftime("%H:%M:%S"), path, e)); self.send_error(502, "pacer: translate failed"); return
                payload = as_stream(cc) if want_stream else json.dumps(cc).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream" if want_stream else "application/json")
                self.end_headers()
                try: self.wfile.write(payload); self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError): pass
                log("%s %s 200 %.1fs (translated%s)" % (time.strftime("%H:%M:%S"), path, time.time() - t0, ", streamed" if want_stream else ""))
                return
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
    ap.add_argument("--reasoning-headroom", type=int, default=4096, help="tokens added to a translated request's output budget for hidden reasoning")
    ap.add_argument("--responses-model", action="append", default=[], help="a model served only by the Responses API: its chat-completions calls are translated (repeatable)")
    ap.add_argument("--header", action="append", default=[], help="'Name: value' added to every upstream request (repeatable)")
    a = ap.parse_args()
    globals()["REASONING_HEADROOM"] = a.reasoning_headroom
    out = open(a.log, "a") if a.log else sys.stderr
    def log(s): out.write(s + "\n"); out.flush()
    log("%s pacer for %s: %s -> %s, %.0f rpm, %d in flight, %d retries" % (time.strftime("%H:%M:%S"), a.provider, a.port, a.upstream, a.rpm, a.concurrency, a.retries))
    Server(("127.0.0.1", a.port), make_handler(a, Pacer(a.rpm, a.concurrency), log)).serve_forever()


if __name__ == "__main__":
    main()
