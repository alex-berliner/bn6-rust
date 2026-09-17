#!/usr/bin/env python3
"""tools/field_names.py — apply the field renames whose evidence we already hold.

The disassembly has ~478 Unk_<NN> fields. src/*.rs, the bn notes in asm/*.s,
docs/coverage and docs/recon name a handful outright; this tool holds the
evidence and applies the rename across include/structs/*.inc,
include/rom_structs/*.inc, asm/*.s and data/*.s (every use must move with the
definition, otherwise the rebuild would break). Old -> new pairs and their
evidence go to reference/bn6f/docs/renames.md.

A field is renamed only if a sentence STATES the role. Hedged or inferred
language ("probably", "looks like") keeps it as Unk_.
"""
import argparse
import os
import re
import sys

# Evidence table. Each entry:
#   (struct_path, struct_macro, old_field, new_field, evidence)
#
# struct_macro is the .macro name within the file whose fields we want to
# rename. The script finds the def_struct_offsets line that names the matching
# struct, gets the prefix from there, and uses it to rewrite every asm/data
# use. (Some .inc files declare several structs; the macro lets us target
# just the right one.)
RENAMES = [
    # The buster barrel pointer. battle.rs:157 states the role outright:
    # "the barrel in oAIData_Unk_68".
    ("include/structs/AIData.inc", "ai_data_struct",
     "Unk_68", "BusterBarrelPtr",
     "battle.rs:157 — \"the barrel in oAIData_Unk_68 (sub_80EB562/sub_80EB572, "
     "asm31.s:108743-108750, spawned on the fire phase's FIRST tick)\""),
    # oAIState fields — Mettaur decision machine. objects.rs:243-250.
    ("include/structs/AIData.inc", "ai_state_struct",
     "Unk_00", "DecideState",
     "objects.rs:243 — \"decide = oAIState_Unk_00, the off_8109FF0 decision-table index\""),
    ("include/structs/AIData.inc", "ai_state_struct",
     "Unk_02", "DecideSubState",
     "objects.rs:244 — \"decide_sub = oAIState_Unk_02, sub_810A0BA's sub-state "
     "(0 = the hop arm sub_810A0D4, 4 = the roll/wait arm sub_810A0EE)\""),
    ("include/structs/AIData.inc", "ai_state_struct",
     "Unk_03", "DecideLatch",
     "objects.rs:246 — \"latch = oAIState_Unk_03, sub_810A0EE's one-shot latch: "
     "0 rolls this frame, 1 counts wander_wait down\""),
    ("include/structs/AIData.inc", "ai_state_struct",
     "Unk_08", "WanderWait",
     "objects.rs:250 — \"wander_wait = oAIState_Unk_08, the losing roll's "
     "idle counter\""),
    # oAIAttackVars fields — per-attack executor fields.
    ("include/structs/AIData.inc", "ai_attack_vars_struct",
     "Unk_00", "AttackStage",
     "gunner.rs:321 — \"oAIAttackVars_Unk_00 (asm32.s:9961): the CurAction-indexed "
     "stage within the current CurAction's arm\""),
    ("include/structs/AIData.inc", "ai_attack_vars_struct",
     "Unk_01", "AttackLatch",
     "gunner.rs:324 — \"oAIAttackVars_Unk_01 (asm32.s:10060): the per-state "
     "one-shot latch (set on first call, cleared on exit — sub_8113002/ai_8113038)\""),
    ("include/structs/AIData.inc", "ai_attack_vars_struct",
     "Unk_0e", "ShotsCount",
     "gunner.rs:390 — \"stage 4 (sub_8112FBA): RelatedObject1Ptr == 1 (cursor "
     "locked) arms CurAnim = 2, the per-shot seed object (dword_8113074 = 0x12810), "
     "and oAIAttackVars_Unk_0e = 3 (SHOTS)\""),
    ("include/structs/AIData.inc", "ai_attack_vars_struct",
     "Unk_10", "AttackWait",
     "objects.rs:251 — \"wait = oAIAttackVars_Unk_10, the CurAction-9 "
     "waiter's countdown\""),
    ("include/structs/AIData.inc", "ai_attack_vars_struct",
     "Unk_18", "AttackRecoverWait",
     "gunner.rs:330 — \"oAIAttackVars_Unk_18 (asm32.s:10109): the CurAction-0x0A "
     "recover counter (24 frames, decremented bgt-style)\""),
    ("include/structs/AIData.inc", "ai_attack_vars_struct",
     "Unk_1a", "HopDone",
     "objects.rs:254 — \"hop_done = oAIAttackVars_Unk_1a, the hop executor's "
     "report: 1 on the commit step (sub_8109DBA), 0 on the refused-move step\""),
    # oObjectSprite_Unk_00 — pending animation index.
    ("include/structs/ObjectSprite.inc", "object_sprite_struct",
     "Unk_00", "CurAnim",
     "spr.rs:427 — \"Write the pending animation index (Unk_00): the port of "
     "sprite_setAnimation (reference/bn6f/asm/sprite.s:1131 -- strb r0, "
     "[r3,#oObjectSprite_Unk_00] after the header-offset shift)\""),
    # oChatbox_Unk_05 — text-script ts_end stack depth.
    ("include/structs/Chatbox.inc", "chatbox_struct",
     "Unk_05", "CbStackDepth",
     "script.rs:1225 — \"CB_NESTED: usize = 0x5; // provenance: derived -- "
     "oChatbox_Unk_05, ts_end's stack depth, Chatbox.inc:18\""),
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BN6F = os.path.join(ROOT, 'reference/bn6f')


def _find_macro_bounds(text, macro_name):
    """Find the start and end line offsets of a .macro macro_name ... .endm block."""
    start = None
    depth = 0
    for i, line in enumerate(text.split('\n')):
        if start is None:
            if re.match(rf'\s*\.macro\s+{re.escape(macro_name)}\b', line):
                start = i
                depth = 1
        else:
            if re.match(r'\s*\.macro\b', line):
                depth += 1
            elif re.match(r'\s*\.endm\b', line):
                depth -= 1
                if depth == 0:
                    return (start, i)
    if start is None:
        raise SystemExit(f"macro {macro_name} not found")
    raise SystemExit(f"macro {macro_name} unbalanced")


def _find_prefix_for(text, macro_name):
    """Find the def_struct_offsets prefix label for the given macro."""
    pat = re.compile(r'def_struct_offsets\s+' + re.escape(macro_name) +
                     r'\s*,\s*(\w+)')
    m = pat.search(text)
    if not m:
        raise SystemExit(f"no def_struct_offsets for {macro_name}")
    return m.group(1)


def _rewrite_field_in_macro(struct_path, macro_name, old_field, new_field):
    """Rewrite the bare field name inside a single macro. Keep the loc comment."""
    full = os.path.join(BN6F, struct_path)
    with open(full) as fp:
        text = fp.read()
    lines = text.split('\n')
    lo, hi = _find_macro_bounds(text, macro_name)
    # The field declaration pattern inside the macro body.
    field_pat = re.compile(
        r'(^\s*(?:u[0-9]+|ptr|bool[0-9]*|enum[0-9]+|flags[0-9]+|u8_arr)\s+)' +
        re.escape(old_field) + r'(\b)')
    n = 0
    for i in range(lo, hi + 1):
        new_line, k = field_pat.subn(lambda m: m.group(1) + new_field + m.group(2),
                                     lines[i])
        if k:
            lines[i] = new_line
            n += k
    if n == 0:
        raise SystemExit(
            f"no rename matched in {struct_path}/{macro_name} for {old_field}")
    with open(full, 'w') as fp:
        fp.write('\n'.join(lines))
    return n


def _rewrite_uses(old_use, new_use):
    """Rewrite the prefixed field name in every asm/data/inc file."""
    files = []
    for sub in ('asm', 'data'):
        d = os.path.join(BN6F, sub)
        for f in sorted(os.listdir(d)):
            if f.endswith('.s'):
                files.append(os.path.join(d, f))
    for sub in ('include/structs', 'include/rom_structs'):
        d = os.path.join(BN6F, sub)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith('.inc'):
                    files.append(os.path.join(d, f))
    total = 0
    for path in files:
        with open(path) as fp:
            text = fp.read()
        if old_use not in text:
            continue
        n = text.count(old_use)
        text = text.replace(old_use, new_use)
        with open(path, 'w') as fp:
            fp.write(text)
        total += n
    return total


def _apply_one(struct_path, macro_name, old_field, new_field):
    full = os.path.join(BN6F, struct_path)
    with open(full) as fp:
        text = fp.read()
    prefix = _find_prefix_for(text, macro_name)
    inc_count = _rewrite_field_in_macro(struct_path, macro_name, old_field, new_field)
    old_use = f"{prefix}_{old_field}"
    new_use = f"{prefix}_{new_field}"
    used = _rewrite_uses(old_use, new_use)
    print(f"  {struct_path}::{macro_name}  {old_field} -> {new_field}  "
          f"({used} use sites)")
    return {
        'struct_path': struct_path,
        'macro_name': macro_name,
        'old_field': old_field,
        'new_field': new_field,
        'prefix': prefix,
        'old_use': old_use,
        'new_use': new_use,
        'uses': used,
    }


def cmd_apply(args):
    results = []
    print("Applying renames:")
    for struct_path, macro, old, new, evidence in RENAMES:
        results.append(_apply_one(struct_path, macro, old, new))
    # Append to docs/renames.md
    md_path = os.path.join(BN6F, 'docs/renames.md')
    with open(md_path) as fp:
        md = fp.read()
    lines = ['', '## D10 — Field renames (2026-09-17)', '',
             'From src/*.rs comments and the bn notes already in the asm/data files.',
             'Each row is a struct-field rename; the old `Unk_<offset>` and the new',
             'name, with the sentence that states the role. Each rename is applied to',
             'the .inc definition and every asm/data use.',
             '',
             '| struct | old field | new field | evidence | use sites |',
             '|---|---|---|---|---|']
    for r in results:
        evidence = next(ev for sp, ma, old, new, ev in RENAMES
                        if sp == r['struct_path'] and ma == r['macro_name']
                        and old == r['old_field'] and new == r['new_field'])
        lines.append(f"| `{r['prefix']}` | `{r['old_field']}` | "
                     f"`{r['new_field']}` | {evidence} | {r['uses']} |")
    md += '\n'.join(lines) + '\n'
    with open(md_path, 'w') as fp:
        fp.write(md)
    print(f"\nAppended {len(results)} renames to docs/renames.md")


def cmd_table(args):
    print(f"{len(RENAMES)} renames held in RENAMES:")
    for struct_path, macro, old, new, evidence in RENAMES:
        print(f"  {struct_path}::{macro}  {old} -> {new}")
        print(f"    evidence: {evidence[:120]}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('apply').set_defaults(func=cmd_apply)
    sub.add_parser('table').set_defaults(func=cmd_table)
    args = p.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()