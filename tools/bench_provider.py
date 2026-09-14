#!/usr/bin/env python3
"""Benchmark a provider against the others on this project's own archived work.

  bench_provider.py run <provider> [--tickets F21b,F27b,...] [--role worker] [--thinking high]
      replays each ticket with the provider's model for that role (tools/replay_bench.py: same base commit,
      same ticket text, verify_rows judges the branch), measuring the provider's balance before and after
      each replay so a subscription's real cost is known in credits, and writes
      docs/benchmarks/provider-<provider>-<stamp>.md with the per-ticket table and totals.
  bench_provider.py table [--tickets ...]
      one table over every replay file in docs/benchmarks/ plus the Muse originals from the ledger:
      per ticket and model, verdict / turns / minutes / nominal $ / real $, and per model the pass rate,
      the nominal and real cost per pass, and minutes per pass.

Real cost: pay-as-you-go = the nominal cost; subscription = credits used x (price_usd_per_month / 30 /
daily_credits) from providers.toml, and when the balance delta is unknown (an older replay, or another
session spending at the same time) it is estimated from the nominal cost at the day's credits-per-dollar rate,
marked "est".
The default ticket set is the five below plus the two already replayed (F18d, F25c): rows of different kinds,
each landed by Muse with a verified number the replay can be judged against.
"""
import argparse, datetime, glob, json, os, re, subprocess, sys, time, tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
DEFAULT = ["F18d", "F25c", "F21b", "F27b", "F34b", "F37c", "F37g"]
HEAD = re.compile(r"^# Replay (\S+) with (\S+) \((\w+)\): (\S+)")
COST = re.compile(r"cost \$([0-9.]+), (\d+) turns, (\d+) min")
CREDITS = re.compile(r"credits used ([0-9.]+)( est)?")


def cfg():
    return tomllib.load(open("providers.toml", "rb"))


def balance(provider):
    p = cfg()["providers"][provider]
    out = subprocess.run(p["probe"], shell=True, capture_output=True, text=True).stdout + ""
    if p["kind"] == "subscription":
        m = re.search(r"remaining ([0-9.]+)", out); return float(m.group(1)) if m else None
    m = re.search(r"remaining \$([0-9.]+)", out); return float(m.group(1)) if m else None


def credit_price(provider):
    p = cfg()["providers"][provider]
    if p["kind"] != "subscription": return None
    return p["price_usd_per_month"] / 30.0 / p["daily_credits"]


def provider_of(model):
    return model.split("/")[0]


def run(a):
    c = cfg(); p = c["providers"][a.provider]
    model = p["roles"][a.role]; stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    doc = "docs/benchmarks/provider-%s-%s.md" % (a.provider, stamp)
    others = subprocess.run("pgrep -fc 'pi -p --approve' || true", shell=True, capture_output=True, text=True).stdout.strip()
    rows = []
    for tid in a.tickets:
        before = balance(a.provider); t0 = time.time()
        r = subprocess.run(["python3", "tools/replay_bench.py", tid, "--model", model, "--thinking", a.thinking, "--role", a.role],
                           capture_output=True, text=True)
        after = balance(a.provider)
        files = sorted(glob.glob("docs/benchmarks/%s-%s-*.md" % (tid, model.split("/")[-1])), key=os.path.getmtime)
        f = files[-1] if files and os.path.getmtime(files[-1]) >= t0 - 5 else None
        verdict, cost, turns, mins = "NO-FILE", 0.0, 0, 0
        if f:
            s = open(f).read(); h = HEAD.search(s); m = COST.search(s)
            verdict = h.group(4) if h else "?"; cost, turns, mins = (float(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (0.0, 0, 0)
            used = (before - after) if (before is not None and after is not None and p["kind"] == "subscription") else None
            if used is not None and others not in ("", "0"):
                with open(f, "a") as fh: fh.write("\nbalance %.1f -> %.1f but %s other pi sessions were spending: credits not attributable\n" % (before, after, others))
                used = None
            elif used is not None:
                with open(f, "a") as fh: fh.write("\ncredits used %.1f (balance %.1f -> %.1f; no other pi session active)\n" % (used, before, after))
        else:
            used = None; print(r.stdout[-500:], r.stderr[-500:])
        rows.append((tid, verdict, cost, turns, mins, used))
        print("%-6s %-6s $%.3f nominal, %d turns, %d min, credits %s" % (tid, verdict, cost, turns, mins, "%.1f" % used if used is not None else "n/a"))
    price = credit_price(a.provider)
    passes = [r for r in rows if r[1] == "PASS"]
    lines = ["# Provider benchmark: %s (%s as %s), %s" % (a.provider, model, a.role, stamp), "",
             "other pi sessions active during the run: %s (a subscription's balance delta then includes their spend)" % others, "",
             "| ticket | verdict | nominal $ | turns | min | credits | real $ |", "|---|---|---|---|---|---|---|"]
    for tid, verdict, cost, turns, mins, used in rows:
        real = (used * price) if (used is not None and price) else (cost if price is None else None)
        lines.append("| %s | %s | %.3f | %d | %d | %s | %s |" % (tid, verdict, cost, turns, mins, "%.1f" % used if used is not None else "n/a", "%.3f" % real if real is not None else "n/a"))
    tot_cost = sum(r[2] for r in rows); tot_used = sum(r[5] for r in rows if r[5] is not None)
    lines += ["", "passes %d of %d; nominal $%.2f total, $%.2f per pass; credits %.1f total%s" % (
        len(passes), len(rows), tot_cost, tot_cost / max(1, len(passes)), tot_used,
        (", real $%.3f total at $%.4f a credit, $%.3f per pass" % (tot_used * price, price, tot_used * price / max(1, len(passes)))) if price else "")]
    open(doc, "w").write("\n".join(lines) + "\n"); print("wrote", doc)


def muse_originals(tickets):
    """the Muse worker sessions that produced each ticket's archived result: cost, turns, minutes (from the ledger)"""
    out = {}
    try:
        rows = json.loads(subprocess.run(["python3", "tools/ticket_ledger.py", "--since", "0", "--json"], capture_output=True, text=True).stdout)
    except ValueError:
        return out
    for r in rows:
        if r["ticket"] in tickets and r["role"] in ("worker", "worker-muse") and r["model"].startswith("muse"):
            o = out.setdefault(r["ticket"], dict(cost=0.0, turns=0, mins=0.0, sessions=0))
            o["cost"] += r["cost"]; o["turns"] += r["turns"]; o["mins"] += r["min"]; o["sessions"] += 1
    return out


def table(a):
    c = cfg(); rate = {}
    per = {}   # (model, ticket) -> (verdict, cost, turns, mins, credits, est)
    for f in glob.glob("docs/benchmarks/F*-*.md"):
        s = open(f).read(); h = HEAD.search(s); m = COST.search(s)
        if not h or not m or h.group(1) not in a.tickets or ":free" in h.group(2): continue
        cr = CREDITS.search(s)
        key = (h.group(2), h.group(1))
        cand = (h.group(4), float(m.group(1)), int(m.group(2)), int(m.group(3)), float(cr.group(1)) if cr else None, bool(cr and cr.group(2)))
        # keep the best replay per model and ticket: PASS over others, then the cheapest
        if key not in per or (cand[0] == "PASS", -cand[1]) > (per[key][0] == "PASS", -per[key][1]): per[key] = cand
    orig = muse_originals(set(a.tickets))
    models = sorted({k[0] for k in per})
    price = {p: credit_price(p) for p in c["providers"]}
    # credits per nominal dollar, from replays that measured a balance delta
    for p in c["providers"]:
        xs = [(v[4], v[1]) for (mo, t), v in per.items() if provider_of(mo) == p and v[4] is not None and v[1] > 0]
        rate[p] = sum(x for x, _ in xs) / sum(y for _, y in xs) if xs else c["providers"][p].get("credits_per_nominal_usd")
    lines = ["| model | " + " | ".join(a.tickets) + " | pass rate | nominal $/pass | real $/pass | min/pass |", "|---|" + "---|" * (len(a.tickets) + 4)]
    lines.append("| muse (original, OpenRouter) | " + " | ".join(("landed, %d turns, %.0f min, $%.2f" % (orig[t]["turns"], orig[t]["mins"], orig[t]["cost"])) if t in orig else "-" for t in a.tickets)
                 + " | - | $%.2f | $%.2f | %.0f |" % ((sum(o["cost"] for o in orig.values()) / max(1, len(orig)),) * 2 + (sum(o["mins"] for o in orig.values()) / max(1, len(orig)),)))
    for mo in models:
        p = provider_of(mo); cells = []; passes = []; 
        for t in a.tickets:
            v = per.get((mo, t))
            if not v: cells.append("-"); continue
            verdict, cost, turns, mins, cr, est = v
            if price.get(p):
                if cr is None and rate.get(p): cr, est = cost * rate[p], True
                real = cr * price[p] if cr is not None else None
            else:
                real = cost
            cells.append("%s, %d turns, %d min, $%.2f%s" % (verdict, turns, mins, real if real is not None else cost, ("" if not est else " est") if real is not None else " nominal"))
            if verdict == "PASS": passes.append((cost, real, mins))
        n = sum(1 for t in a.tickets if (mo, t) in per)
        if passes:
            nom = sum(x[0] for x in passes) / len(passes); rl = [x[1] for x in passes if x[1] is not None]
            real = sum(rl) / len(rl) if rl else None; mins = sum(x[2] for x in passes) / len(passes)
            tail = "%d/%d | $%.2f | %s | %.0f |" % (len(passes), n, nom, ("$%.3f" % real) if real is not None else "n/a", mins)
        else:
            tail = "0/%d | - | - | - |" % n
        lines.append("| %s | %s | %s" % (mo, " | ".join(cells), tail))
    note = "Real $ for a subscription = credits x (%s); credits marked from a balance delta where measured, else estimated at the provider's measured credits-per-dollar rate." % ", ".join(
        "%s $%.4f/credit" % (p, v) for p, v in price.items() if v)
    print("\n".join(lines)); print(); print(note)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("provider"); r.add_argument("--tickets", default=",".join(DEFAULT[2:]))
    r.add_argument("--role", default="worker"); r.add_argument("--thinking", default="high")
    t = sub.add_parser("table"); t.add_argument("--tickets", default=",".join(DEFAULT))
    a = ap.parse_args(); a.tickets = [x for x in a.tickets.split(",") if x]
    {"run": run, "table": table}[a.cmd](a)


if __name__ == "__main__":
    main()
