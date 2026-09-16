#!/usr/bin/env python3
"""providers.toml as a tool: resolves a run profile's jobs to models by current budget, renders the pi agent
files, checks a provider's budget, and prints a run's instruction.

  roles.py check                          validate the file; exit 1 with the reasons
  roles.py resolve <run>                  "<role> <model>" per job: the first candidate whose provider can start
                                          work now (probes each provider once; a provider whose probe errors
                                          is skipped); exit 1 if the coordinator or worker resolves to nothing
  roles.py model <run> <role> [--tail]    one resolved model id; --tail accepts any provider above its
                                          stop_below (a one-shot session's need), not only start_above
  roles.py render [<run> ...]             write .pi/agents/<role>-<run>.md (worker, verifier, recon) from
                                          .pi/roles/<role>.md with the resolved models, plus bare <role>.md
                                          aliases for the first scheduled run; default: every run
  roles.py instruction <run>              the coordinator instruction naming that run's roles
  roles.py providers <run>                the providers of the resolved coordinator and worker (the watcher's set)
  roles.py budget <provider> --start|--stop
                                          exit 0 when the provider can start work / keep working, 1 when not,
                                          2 when its probe failed (never treated as exhausted)
  roles.py workers <run>                  the worker slots the run should have in flight right now: its `workers`
                                          number, or for `workers = "pace"` the surplus rule (below); the
                                          coordinator asks each cycle, so slots follow the budget through the day
  roles.py schedule                       shell lines: RUNS="hyper" PARALLEL=0 RESERVE="openrouter"

The pacing rule (a subscription with `reset = "daily HH:MM"`): remaining balance R (its probe), hours H to the
reset, the reserve = coordinator_credits_per_hour x H for every other scheduled profile whose coordinator's first
candidate is on this provider (that coordination comes first, however the other profile's own budget fares),
surplus = R - stop_below - reserve; slots = ceil(surplus / (H x worker_credits_per_hour)), clamped to
[pace_min, pace_max], 0 when the surplus is gone. Rolling windows (`reset = "rolling 5h"`) are never paced:
they are used whenever open.
  roles.py first                          the first scheduled run
"""
import functools, os, re, subprocess, sys, tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROLES = ("coordinator", "worker", "verifier", "recon", "judge", "auditor", "digest")
AGENT_ROLES = ("worker", "verifier", "recon")


def load():
    return tomllib.load(open(os.path.join(ROOT, "providers.toml"), "rb"))


def first(cfg):
    return cfg["schedule"]["runs"][0]


def provider_of(model):
    return model.split("/")[0]


def expired(cfg, provider):
    """a subscription with an `expires` date in the past can buy nothing, whatever its probe says"""
    import datetime
    d = cfg["providers"][provider].get("expires")
    try: return bool(d) and datetime.date.fromisoformat(str(d)) < datetime.date.today()
    except ValueError: return False


def budget(cfg, provider, phase):
    """0 ok, 1 no budget, 2 probe error; prints the probe's last line. Phases: --start (a run may start),
    --stop (a run may keep going), --tail (a one-shot session may run: stop_below plus the provider's oneshot_flags)"""
    p = cfg["providers"][provider]
    if expired(cfg, provider):
        print("%s: the plan expired on %s" % (provider, p.get("expires"))); return 1
    if p["kind"] == "subscription":
        need = p["start_above"] if phase == "--start" else p["stop_below"]
        extra = (" " + p["oneshot_flags"]) if phase == "--tail" and p.get("oneshot_flags") else ""
        r = subprocess.run(p["probe"] + " --min %s%s" % (need, extra), shell=True, capture_output=True, text=True, cwd=ROOT)
        out = (r.stdout + r.stderr).strip(); print(out.splitlines()[-1] if out else "(no probe output)")
        return 0 if r.returncode == 0 else (1 if r.returncode == 1 else 2)
    r = subprocess.run(p["probe"], shell=True, capture_output=True, text=True, cwd=ROOT)
    out = (r.stdout + r.stderr).strip(); line = out.splitlines()[-1] if out else ""; print(line or "(no probe output)")
    m = re.search(r"remaining \$([0-9.]+)", line)
    if r.returncode not in (0, 1) or not m: return 2
    need = p.get("floor_usd", 0.0) + (p.get("start_above", 1.0) if phase == "--start" else 0.0)
    return 0 if float(m.group(1)) > need else 1


@functools.lru_cache(maxsize=None)
def can_start(provider, phase="--start"):
    """--start: above start_above; --tail (or --stop): above stop_below, enough for a one-shot session"""
    cfg = load()
    if provider not in cfg["providers"]: return False
    with open(os.devnull, "w") as devnull:
        old = sys.stdout; sys.stdout = devnull
        try: rc = budget(cfg, provider, phase if phase in ("--start", "--tail") else "--stop")
        finally: sys.stdout = old
    return rc == 0


def resolve(cfg, run, phase="--start"):
    """role -> model (or None): the first candidate whose provider has budget at that phase"""
    r = cfg["runs"][run]; out = {}
    for role in ROLES:
        out[role] = next((m for m in r.get(role, []) if can_start(provider_of(m), phase)), None)
    return out


def render(cfg, runs):
    out_dir = os.path.join(ROOT, ".pi", "agents"); os.makedirs(out_dir, exist_ok=True); written = []
    for run in runs:
        res = resolve(cfg, run)
        for role in AGENT_ROLES:
            model = res[role] or cfg["runs"][run][role][0]     # nothing can start: render the first candidate anyway
            tpl = open(os.path.join(ROOT, ".pi", "roles", role + ".md")).read()
            fm, body = tpl.split("---\n", 2)[1], tpl.split("---\n", 2)[2]
            for name in [role + "-" + run] + ([role] if run == first(cfg) else []):
                head = "name: %s\n%s\nmodel: %s" % (name, fm.rstrip("\n"), model)
                note = "<!-- generated by tools/roles.py from providers.toml (run %s) and .pi/roles/%s.md; edit those, not this -->\n" % (run, role)
                open(os.path.join(out_dir, name + ".md"), "w").write("---\n%s\n---\n%s%s" % (head, note, body)); written.append(name)
    if set(runs) == set(cfg["runs"]):
        for f in os.listdir(out_dir):
            p = os.path.join(out_dir, f)
            if f.endswith(".md") and f[:-3] not in written and "generated by tools/roles.py" in open(p).read():
                os.remove(p); print("removed stale", f)
    print("rendered:", " ".join(written))


def instruction(cfg, run):
    res = resolve(cfg, run); r = cfg["runs"][run]
    provs = sorted({provider_of(m) for m in (res["coordinator"], res["worker"]) if m})
    money = []
    for p in provs:
        pc = cfg["providers"][p]
        if pc["kind"] == "subscription":
            money.append("%s is a subscription with a daily balance the user wants spent to the end (a watcher outside you stops the run when it is gone)" % p)
        else:
            money.append("%s is pay as you go with a hard cap per run enforced outside you and a floor of $%.2f on the account" % (p, pc.get("floor_usd", 0.0)))
    n = workers(cfg, run)
    slots = ("%d workers in flight" % n) if isinstance(r["workers"], int) else (
        "as many workers in flight as `python3 tools/roles.py workers %s` prints, asked before every dispatch (it follows the "
        "day's budget; %d right now; if it prints 0, let the tickets in flight finish and STOP)" % (run, n))
    return ("Run the loop with %s. The roles for this run are worker-%s, verifier-%s and recon-%s: dispatch "
            "tickets to worker-%s, claims beyond harness lines to verifier-%s, code questions to recon-%s, and nothing to any "
            "other role. Use `python3 tools/next_ticket.py --pair %d --claim`. %s; never stop for budget reasons yourself. The "
            "phase is porting: the queue is whatever next_ticket.py returns until none is OPEN (then the judge refill in your "
            "instructions). Each landing keeps the full table identical (every isolated row 0; cursor's single-frame tear moves "
            "with the ROM layout and is reported, not chased), verified with tools/verify_rows.py and the trace as the tickets "
            "say; the verifier only when the branch merges and a claim needs it. Commits arriving on main from the human session "
            "or another run are normal. No model overrides beyond the roles named."
            % (slots, run, run, run, run, run, run, max(n, 1), "; ".join(money)))


def hours_to_reset(spec):
    """'daily HH:MM' -> hours from now to the next such time (local); None for anything else"""
    import datetime
    m = re.match(r"daily (\d{1,2}):(\d{2})$", spec or "")
    if not m: return None
    now = datetime.datetime.now(); t = now.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    if t <= now: t += datetime.timedelta(days=1)
    return (t - now).total_seconds() / 3600.0


def remaining(cfg, provider):
    p = cfg["providers"][provider]
    out = subprocess.run(p["probe"], shell=True, capture_output=True, text=True, cwd=ROOT).stdout
    m = re.search(r"remaining \$?([0-9.]+)", out); return float(m.group(1)) if m else None


def workers(cfg, run):
    import math
    r = cfg["runs"][run]; w = r["workers"]
    if isinstance(w, int): return w
    if w != "pace": sys.exit("runs.%s.workers must be an integer or \"pace\"" % run)
    prov = provider_of(r["worker"][0]); p = cfg["providers"][prov]
    H = hours_to_reset(p.get("reset")); R = remaining(cfg, prov)
    if H is None or R is None: return r.get("pace_min", 0)      # no daily reset or no balance: nothing to pace on
    reserve = sum(p.get("coordinator_credits_per_hour", 0) * H for other, o in cfg["runs"].items()
                  if other != run and other in cfg["schedule"]["runs"] and provider_of(o["coordinator"][0]) == prov)
    surplus = R - p.get("stop_below", 0) - reserve
    n = math.ceil(surplus / (H * p.get("worker_credits_per_hour", 20))) if surplus > 0 else 0
    return max(r.get("pace_min", 0), min(r.get("pace_max", 4), n))


def check(cfg):
    bad = []; s = cfg.get("schedule", {})
    for key in ("runs", "parallel", "reserve"):
        if key not in s: bad.append("schedule.%s missing" % key)
    for run in s.get("runs", []) + s.get("reserve", []):
        if run not in cfg.get("runs", {}): bad.append("schedule names unknown run %r" % run)
    for prov, p in cfg.get("providers", {}).items():
        if p.get("kind") not in ("subscription", "payg"): bad.append("providers.%s.kind must be subscription or payg" % prov)
        if "probe" not in p: bad.append("providers.%s.probe missing" % prov)
        if p.get("kind") == "subscription" and not all(k in p for k in ("start_above", "stop_below")): bad.append("providers.%s needs start_above and stop_below" % prov)
        if p.get("kind") == "payg" and "floor_usd" not in p: bad.append("providers.%s needs floor_usd" % prov)
    for run, r in cfg.get("runs", {}).items():
        if not ((isinstance(r.get("workers"), int) and r["workers"] >= 1) or r.get("workers") == "pace"): bad.append("runs.%s.workers must be a positive integer or \"pace\"" % run)
        if r.get("workers") == "pace" and provider_of(r["worker"][0]) in cfg.get("providers", {}) and not str(cfg["providers"][provider_of(r["worker"][0])].get("reset", "")).startswith("daily"):
            bad.append("runs.%s: workers = \"pace\" needs a `reset = \"daily HH:MM\"` on provider %s" % (run, provider_of(r["worker"][0])))
        for role in ROLES:
            c = r.get(role)
            if not isinstance(c, list) or not c: bad.append("runs.%s.%s must be a non-empty list of model ids" % (run, role)); continue
            for m in c:
                if "/" not in m: bad.append("runs.%s.%s: %r is not provider/model" % (run, role, m))
                elif provider_of(m) not in cfg.get("providers", {}): bad.append("runs.%s.%s: %r names a provider not in [providers]" % (run, role, m))
    for role in AGENT_ROLES:
        if not os.path.exists(os.path.join(ROOT, ".pi", "roles", role + ".md")): bad.append(".pi/roles/%s.md missing" % role)
    if bad: print("\n".join("providers.toml: " + b for b in bad)); return 1
    joint = [run for run, r in cfg["runs"].items() if len({provider_of(m) for role in ROLES for m in r[role]}) > 1]
    print("providers.toml ok: runs %s (parallel %s), reserve %s%s" % (s["runs"], s["parallel"], s["reserve"], ("; joint runs: %s" % joint) if joint else ""))
    return 0


def main():
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    cfg = load(); cmd = a[0]
    if cmd == "check": sys.exit(check(cfg))
    elif cmd == "first": print(first(cfg))
    elif cmd == "schedule":
        s = cfg["schedule"]; print('RUNS="%s"\nPARALLEL=%d\nRESERVE="%s"' % (" ".join(s["runs"]), 1 if s["parallel"] else 0, " ".join(s["reserve"])))
    elif cmd == "budget": sys.exit(budget(cfg, a[1], a[2] if len(a) > 2 else "--start"))
    elif cmd == "resolve":
        res = resolve(cfg, a[1], "--tail" if "--tail" in a else "--start")
        for role, m in res.items(): print("%-12s %s" % (role, m or "(no candidate can start)"))
        sys.exit(0 if res["coordinator"] and res["worker"] else 1)
    elif cmd == "model":
        m = resolve(cfg, a[1], "--tail" if "--tail" in a else "--start")[a[2]]
        if not m: sys.exit("no candidate for %s of run %s has budget now" % (a[2], a[1]))
        print(m)
    elif cmd == "workers": print(workers(cfg, a[1]))
    elif cmd == "providers":
        res = resolve(cfg, a[1]); print(" ".join(sorted({provider_of(m) for m in (res["coordinator"], res["worker"]) if m})))
    elif cmd == "render": render(cfg, a[1:] or list(cfg["runs"]))
    elif cmd == "instruction": print(instruction(cfg, a[1]))
    else: sys.exit("unknown command %r\n%s" % (cmd, __doc__))


if __name__ == "__main__":
    main()
