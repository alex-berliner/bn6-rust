#!/usr/bin/env bash
# Decompile the real MMBN6F cartridge image with Ghidra, headlessly, using the
# reference/bn6f disassembly's own symbols, and write one C file per function to
# decomp/.
#
#   tools/ghidra_decompile.sh            # full run: import, analyse, decompile
#   tools/ghidra_decompile.sh --resume   # reuse the analysed project, decompile only
#   tools/ghidra_decompile.sh --symbols-only   # just regenerate the symbol TSVs
#
# Nothing here touches the repo except decomp/ (gitignored) and nothing here
# writes inside reference/bn6f -- the submodule is read-only to this script.
#
# The ROM is copyrighted: it is read from $BN_ROM in place, never copied into the
# repo, and the C it produces is a local reading aid that must stay untracked.
#
# Environment:
#   BN_ROM             cartridge image to decompile   (/tmp/bn6f_real.gba)
#   BN_ROM_SHA1        expected sha1, checked before anything else
#   GHIDRA_DIR         Ghidra install                 (/home/box/opt/ghidra_*)
#   BN_GHIDRA_PROJECTS project directory              (/home/box/opt/ghidra-projects)
#   BN_DECOMP_OUT      output directory               (<repo>/decomp)
#   BN_DECOMP_THREADS  decompiler threads             (cores - 1)
#   BN_DECOMP_TIMEOUT  seconds per function           (120)
#   BN_DECOMP_PARAM_ID 1 = run Decompiler Parameter ID: better parameter and
#                      return types, at the cost of a second whole-program
#                      decompile pass during analysis
#   BN_ANALYSIS_TIMEOUT  seconds for auto-analysis    (7200)

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

BN_ROM="${BN_ROM:-/tmp/bn6f_real.gba}"
BN_ROM_SHA1="${BN_ROM_SHA1:-0676ecd4d58a976af3346caebb44b9b6489ad099}"
BN_GHIDRA_PROJECTS="${BN_GHIDRA_PROJECTS:-/home/box/opt/ghidra-projects}"
BN_DECOMP_OUT="${BN_DECOMP_OUT:-$REPO/decomp}"
BN_DECOMP_THREADS="${BN_DECOMP_THREADS:-}"
BN_ANALYSIS_TIMEOUT="${BN_ANALYSIS_TIMEOUT:-7200}"
PROJECT_NAME="${BN_GHIDRA_PROJECT_NAME:-bn6f}"
# Ghidra names the imported program after the file, so --resume must too.
PROGRAM_NAME="$(basename "${BN_ROM:-/tmp/bn6f_real.gba}")"
REF="$REPO/reference/bn6f"
SCRIPTS="$REPO/tools/ghidra"

# The base address a GBA cartridge is mapped at, and the processor the console
# runs: an ARM7TDMI, i.e. ARMv4 with Thumb.
ROM_BASE=0x08000000
LANGUAGE="ARM:LE:32:v4t"
COMPILER="default"

MODE=full
for arg in "$@"; do
	case "$arg" in
		--resume) MODE=resume ;;
		--symbols-only) MODE=symbols ;;
		-h|--help) sed -n '2,32p' "${BASH_SOURCE[0]}"; exit 0 ;;
		*) echo "ghidra_decompile: unknown argument $arg" >&2; exit 2 ;;
	esac
done

die() { echo "ghidra_decompile: $*" >&2; exit 1; }
say() { echo "ghidra_decompile: $*"; }

# ---------------------------------------------------------------------------
# Locate Ghidra
# ---------------------------------------------------------------------------
if [[ -z "${GHIDRA_DIR:-}" ]]; then
	# Newest ghidra_* under /home/box/opt.
	GHIDRA_DIR="$(ls -d /home/box/opt/ghidra_*_PUBLIC 2>/dev/null | sort -V | tail -1 || true)"
fi
[[ -n "$GHIDRA_DIR" && -x "$GHIDRA_DIR/support/analyzeHeadless" ]] \
	|| die "no Ghidra install found; set GHIDRA_DIR (looked under /home/box/opt)"
HEADLESS="$GHIDRA_DIR/support/analyzeHeadless"

# Ghidra needs a JDK, not just a JRE.  launch.properties records which one; if
# that is unset, fall back to any JDK beside the Ghidra install.
if ! grep -q '^JAVA_HOME_OVERRIDE=.\+' "$GHIDRA_DIR/support/launch.properties" 2>/dev/null; then
	if [[ -z "${JAVA_HOME:-}" ]]; then
		JAVA_HOME="$(ls -d /home/box/opt/jdk-* 2>/dev/null | sort -V | tail -1 || true)"
		[[ -n "$JAVA_HOME" ]] || die "no JDK found: set JAVA_HOME or JAVA_HOME_OVERRIDE in $GHIDRA_DIR/support/launch.properties"
		export JAVA_HOME
	fi
	say "using JDK $JAVA_HOME"
fi

# ---------------------------------------------------------------------------
# Check the inputs
# ---------------------------------------------------------------------------
[[ -f "$BN_ROM" ]] || die "ROM not found at $BN_ROM (set BN_ROM)"
actual_sha1="$(sha1sum "$BN_ROM" | cut -d' ' -f1)"
if [[ -n "$BN_ROM_SHA1" && "$actual_sha1" != "$BN_ROM_SHA1" ]]; then
	die "ROM sha1 mismatch at $BN_ROM: got $actual_sha1, expected $BN_ROM_SHA1.
	     Decompiling the wrong image would put wrong addresses beside every
	     symbol.  Set BN_ROM_SHA1= to override deliberately."
fi
say "ROM $BN_ROM sha1 $actual_sha1 ok ($(stat -c%s "$BN_ROM") bytes)"
[[ -d "$REF/asm" ]] || die "reference/bn6f not checked out (git submodule update --init)"

# ---------------------------------------------------------------------------
# Symbols
# ---------------------------------------------------------------------------
WORK="$BN_GHIDRA_PROJECTS/$PROJECT_NAME.work"
mkdir -p "$WORK" "$BN_GHIDRA_PROJECTS" "$BN_DECOMP_OUT"
SYMBOLS="$WORK/symbols.tsv"
MEMMAP="$WORK/memmap.tsv"

say "indexing reference/bn6f ..."
python3 "$SCRIPTS/bnsyms.py" --ref "$REF" --rom "$BN_ROM" \
	--out "$SYMBOLS" --out-mem "$MEMMAP"
[[ "$MODE" == symbols ]] && { say "--symbols-only: stopping after $SYMBOLS"; exit 0; }

# ---------------------------------------------------------------------------
# Ghidra
# ---------------------------------------------------------------------------
THREAD_ARG=()
[[ -n "$BN_DECOMP_THREADS" ]] && THREAD_ARG=("$BN_DECOMP_THREADS")

LOG="$WORK/ghidra.log"
SCRIPTLOG="$WORK/ghidra-script.log"
start=$(date +%s)

if [[ "$MODE" == resume ]]; then
	say "resuming: decompiling from the existing project (no re-import, no re-analysis)"
	"$HEADLESS" "$BN_GHIDRA_PROJECTS" "$PROJECT_NAME" \
		-process "$PROGRAM_NAME" \
		-noanalysis \
		-readOnly \
		-scriptPath "$SCRIPTS" \
		-postScript BnDecompile.java "$SYMBOLS" "$BN_DECOMP_OUT" "${THREAD_ARG[@]}" \
		-log "$LOG" -scriptlog "$SCRIPTLOG" \
		-max-cpu "$(nproc)"
else
	say "importing $BN_ROM at $ROM_BASE as $LANGUAGE and analysing"
	say "  project  $BN_GHIDRA_PROJECTS/$PROJECT_NAME"
	say "  output   $BN_DECOMP_OUT"
	"$HEADLESS" "$BN_GHIDRA_PROJECTS" "$PROJECT_NAME" \
		-import "$BN_ROM" \
		-overwrite \
		-processor "$LANGUAGE" \
		-cspec "$COMPILER" \
		-loader BinaryLoader \
		-loader-baseAddr "$ROM_BASE" \
		-scriptPath "$SCRIPTS" \
		-preScript BnPrepare.java "$MEMMAP" "$SYMBOLS" \
		-postScript BnDecompile.java "$SYMBOLS" "$BN_DECOMP_OUT" "${THREAD_ARG[@]}" \
		-analysisTimeoutPerFile "$BN_ANALYSIS_TIMEOUT" \
		-log "$LOG" -scriptlog "$SCRIPTLOG" \
		-max-cpu "$(nproc)"
fi

elapsed=$(( $(date +%s) - start ))

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
INDEX="$BN_DECOMP_OUT/index.tsv"
say "wall time ${elapsed}s"
if [[ -f "$INDEX" ]]; then
	awk -F'\t' '
		/^#/ { next }
		{ n++ }
		$6 == "ok"      { ok++; bytes += $7; lines += $8; if ($4 == "declared") decl++ }
		$6 == "failed"  { bad++ }
		$6 == "absent"  { absent++ }
		$4 == "spurious" { spur++ }
		$4 == "empty"    { empty++ }
		END {
			printf "ghidra_decompile: %d rows -- %d C files written (%d of them the ", n, ok, decl
			printf "disassembly'"'"'s own functions), %d failed, %d declared but absent\n", bad, absent
			printf "ghidra_decompile: dropped %d functions analysis invented in data, ", spur
			printf "%d with an empty body\n", empty
			printf "ghidra_decompile: %.1f MiB of C, %d lines\n", bytes/1048576, lines
		}' "$INDEX"
	say "read it with:  python3 tools/csrc.py <symbol-or-address>"
else
	die "no $INDEX -- see $LOG and $SCRIPTLOG"
fi
