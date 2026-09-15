#!/usr/bin/env python3
"""New slides for the learn feed (web/learn/slides.js), written by a model under the feed's rules and checked
mechanically before they are appended: N slides on how existing code works (parts no slide covers yet) and
N on the code that landed in the last day (how it works now, never the process). Part of the 09:15 roundup.

  python3 tools/learn_slides.py [--existing 6] [--recent 6] [--since 24] [--model provider/model] [--post] [--dry-run]

Checks every slide must pass (a failing slide is dropped, and the reasons are printed):
  - code is a real excerpt: every non-blank line of it (except "// ..." markers) occurs, whitespace-trimmed, in
    the file codePath names under src/; at most 22 lines
  - no image; title has no numbers; text is 45 to 130 words
  - 3 to 5 highlights, each half an exact substring occurring exactly once in the slide's code / text
  - every hex value or number of two or more digits in the text is followed by words in the same sentence
    (an explanation), and no number appears bare at the start of the text
The model comes from the first scheduled run profile whose digest job can run at the one-shot (--tail) level.
"""
import argparse, glob, json, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
SLIDES = "web/learn/slides.js"


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def rules():
    s = open(SLIDES).read(); return s[:s.index("const SLIDES")] if "const SLIDES" in s else s[:3000]


def titles():
    return re.findall(r'^\s*title:\s*"((?:[^"\\]|\\.)*)"', open(SLIDES).read(), re.M)


def pick_model(explicit):
    if explicit: return explicit
    import tomllib
    for run in tomllib.load(open("providers.toml", "rb"))["schedule"]["runs"]:
        r = subprocess.run(["python3", "tools/roles.py", "model", run, "digest", "--tail"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip(): return r.stdout.strip()
    return None


def ask(model, prompt):
    p = subprocess.run(["pi", "-p", "--approve", "--no-session", "--mode", "json", "--model", model, "--thinking", "medium",
                        "--tools", "read,grep,find,ls", prompt], capture_output=True, text=True, timeout=1500, stdin=subprocess.DEVNULL)
    last, cost = "", 0.0
    for line in p.stdout.splitlines():
        try: e = json.loads(line)
        except ValueError: continue
        if e.get("type") not in ("turn_end", "message_end"): continue
        m = e.get("message") or {}
        if m.get("role") != "assistant": continue
        if e.get("type") == "turn_end": cost += ((m.get("usage") or {}).get("cost") or {}).get("total", 0) or 0
        t = " ".join(c.get("text", "") for c in m.get("content", []) if c.get("type") == "text").strip()
        if t: last = t
    os.makedirs("/tmp/bn-learn", exist_ok=True)
    open("/tmp/bn-learn/reply-%s.txt" % re.sub(r"\W", "_", prompt[-40:]), "w").write(last)
    return [x for x in json_objects(last) if isinstance(x, dict) and "title" in x], cost


def json_objects(text):
    """every top-level {...} in a reply, by brace matching (string-aware), whatever surrounds them"""
    out, depth, start, in_str, esc = [], 0, None, False, False
    for i, ch in enumerate(text):
        if in_str:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': in_str = False
            continue
        if ch == '"': in_str = True
        elif ch == "{":
            if depth == 0: start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try: out.append(json.loads(text[start:i + 1]))
                except ValueError: pass
                start = None
    return out


NUM = re.compile(r"0x[0-9a-fA-F]+|\d{2,}")
JARGON = ("sequencer", "executor", "handler", "descriptor", "oracle", "harness", "canon", "fixture", "opcode", "dispatch", "predicate",
          "gate", "gating", "edge", "state machine", "callback", "hunk", "residue", "regression", "trace", "sub_")
EXPLAINERS = (" is ", " are ", " means ", "that is,", "in other words", "which is", ": ", " — ", " -- ", "(")


def check(slide, known):
    why = []
    for k in ("title", "codePath", "code", "text", "highlights"):
        if not slide.get(k): why.append("missing " + k)
    if why: return why
    if "image" in slide: slide.pop("image"); slide.pop("imageAlt", None)
    if slide["title"] in known: why.append("duplicate title")
    if re.search(r"\d", slide["title"]): why.append("number in the title")
    path = slide["codePath"].strip()
    if not (path.startswith("src/") and os.path.exists(path)): why.append("codePath not a file under src/: %r" % path)
    else:
        real = {l.strip() for l in open(path).read().splitlines() if l.strip()}
        lines = [l for l in slide["code"].splitlines() if l.strip()]
        if len(lines) > 22: why.append("code longer than 22 lines")
        fake = [l for l in lines if l.strip() not in real and not l.strip().startswith("// ...")]
        if fake: why.append("code not an excerpt of %s: %r" % (path, fake[:2]))
    words = len(slide["text"].split())
    if not 45 <= words <= 130: why.append("text is %d words (45-130)" % words)
    hs = slide["highlights"]
    if not isinstance(hs, list) or not 3 <= len(hs) <= 5: why.append("need 3 to 5 highlights")
    else:
        for h in hs:
            c, t = h.get("code", ""), h.get("text", "")
            if slide["code"].count(c) != 1: why.append("highlight code not exactly once: %r" % c[:40])
            if slide["text"].count(t) != 1: why.append("highlight text not exactly once: %r" % t[:40])
    text = slide["text"]
    low = text.lower()
    for j in JARGON:
        if j in low:
            sent = next((x for x in re.split(r"(?<=[.!?])\s+", text) if j in x.lower()), "")
            if not any(e in sent for e in EXPLAINERS): why.append("jargon %r used without explaining it in its sentence" % j)
    if NUM.match(text.strip()): why.append("text starts with a bare number")
    for m in NUM.finditer(text):
        tail = text[m.end():]; sentence = re.split(r"[.!?](?:\s|$)", tail, 1)[0]
        if len(sentence.split()) < 3: why.append("number %s is not explained in its sentence" % m.group(0))
    return why


def to_js(slide):
    out = ["{", '  title: %s,' % json.dumps(slide["title"]), '  codePath: %s,' % json.dumps(slide["codePath"]),
           '  code: %s,' % json.dumps(slide["code"]), '  text: %s,' % json.dumps(slide["text"]), "  highlights: ["]
    for h in slide["highlights"]:
        out.append("    { code: %s,\n      text: %s }," % (json.dumps(h["code"]), json.dumps(h["text"])))
    out += ["  ],", "},"]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--existing", type=int, default=6); ap.add_argument("--recent", type=int, default=6)
    ap.add_argument("--since", type=int, default=24); ap.add_argument("--model"); ap.add_argument("--post", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    model = pick_model(a.model)
    if not model: print("learn_slides: no model with budget for a one-shot session; nothing written"); return
    known = titles()
    recent = sh("git log --since='%d hours ago' --format='%%h %%s' -- src | head -30" % a.since)
    stat = sh("git diff --stat \"HEAD@{%d hours ago}\" HEAD -- src 2>/dev/null | tail -25" % a.since) or sh("git log --since='%d hours ago' --format= --name-only -- src | sort | uniq -c | sort -rn | head -20" % a.since)
    schema = ('Reply with ONLY the slides, one JSON object per line (JSON Lines, no array, no code fences, no prose), each {"title","codePath","code","text","highlights":[{"code","text"},...]}; newlines inside code are written as \\n. '
              'No image. codePath is a path under src/ and code is copied verbatim from that file (about 12 to 18 lines; a line "// ..." '
              'may mark something left out, and the text must say what). text is 60 to 100 words of plain English explaining how this '
              'part of the code works today, for a reader with a short attention span and no jargon; every number or hex value you '
              'write in the text must be explained in the same sentence (what it counts, in plain words), and no number may appear in '
              'the title. highlights are 3 to 5 pairs; each code half is an exact substring of this slide\'s code occurring exactly once, '
              'each text half an exact substring of this slide\'s text occurring exactly once, pointing at the concrete thing the sentence '
              'talks about. Never describe the project\'s process, tickets, agents or history: only how the code works. The reader has '
              'never seen this project or a game engine: write the way the Dolphin emulator\'s progress reports do, saying what a thing is '
              'before saying what the code does with it; words such as sequencer, executor, handler, descriptor, gate, edge, state machine, '
              'fixture or harness may appear only in a sentence that says in plain words what they mean here.')
    intro = "Rules of the learn feed (from the top of web/learn/slides.js):\n%s\n\nSlides already in the feed (do not repeat their subjects):\n- %s\n\n" % (rules(), "\n- ".join(known))
    slides, cost = [], 0.0
    def batches(n):
        while n > 0: yield min(3, n); n -= 3

    def ask2(model, prompt):
        arr, c = ask(model, prompt)
        if not arr:
            arr2, c2 = ask(model, prompt); arr, c = arr2, c + c2
        return arr, c
    for n in batches(a.existing):
        arr, c = ask2(model, intro + schema + ("\n\nWrite %d slides about parts of src/ that no existing slide covers (read the files first: src/*.rs). "
                                             "Prefer the pieces a curious reader would ask about: how a frame is drawn, how input becomes an action, "
                                             "how the harness compares pixels, how a chip resolves, how an enemy decides. Subjects already used this "
                                             "morning: %s") % (n, [x[1].get("title") for x in slides]))
        cost += c; slides += [("existing", s) for s in arr]
    for n in batches(a.recent):
        arr, c = ask2(model, intro + schema + ("\n\nWrite %d slides about the code that landed in the last %d hours, explaining how it works now "
                                             "(not that it changed, not who changed it). The commits touching src/ in that window:\n%s\n"
                                             "Files changed:\n%s\nRead the current files before writing. Subjects already used this morning: %s")
                                             % (n, a.since, recent, stat, [x[1].get("title") for x in slides]))
        cost += c; slides += [("recent", s) for s in arr]
    kept, dropped = [], []
    for kind, s in slides:
        if not isinstance(s, dict): dropped.append((kind, "?", ["not an object"])); continue
        why = check(s, known + [k["title"] for k in kept])
        (kept.append(s) if not why else dropped.append((kind, s.get("title", "?"), why)))
    print("learn_slides: model %s, nominal $%.3f; kept %d of %d" % (model, cost, len(kept), len(slides)))
    for kind, t, why in dropped: print("  dropped (%s) %r: %s" % (kind, t, "; ".join(why)[:200]))
    for s in kept: print("  kept: %s (%s)" % (s["title"], s["codePath"]))
    if a.dry_run or not kept:
        if a.dry_run: json.dump(kept, open("/tmp/learn_slides_preview.json", "w"), indent=1); print("preview in /tmp/learn_slides_preview.json")
        return
    js = open(SLIDES).read(); end = js.rstrip().rfind("];"); assert end > 0
    js = js[:end].rstrip() + "\n\n" + "\n\n".join(to_js(s) for s in kept) + "\n\n];\n"
    open(SLIDES, "w").write(js); print("appended %d slides to %s" % (len(kept), SLIDES))
    if a.post:
        msg = "learn: %d new slides (%s)" % (len(kept), "; ".join(s["title"] for s in kept)[:300])
        print(sh("exec 9>/tmp/bn-land.lock; flock -w 600 9 && git add web/learn/slides.js && git commit -q -m %s && git push -q origin main && bash tools/publish_site.sh --no-build | tail -1" % json.dumps(msg + "\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>")))


if __name__ == "__main__":
    main()
