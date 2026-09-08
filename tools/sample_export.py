"""Export a DirectSound SAMPLE -- an M4A/MP2K `WaveData` -- from the disassembly to a WAV.

usage: python3 sample_export.py <symbol-or-address> [out.wav]

  python3 sample_export.py byte_81597A0 assets/buster_hit.wav
  python3 sample_export.py SOUND_HIT_6B assets/buster_hit.wav   # alias, see ALIASES below
  python3 sample_export.py 0x081597A0                           # prints the header, writes nothing

Unlike `chip_export.py` or `banner_export.py`, this needs no real ROM: a `WaveData` is a
plain labelled blob in the disassembly's own `data/dat*.s` files, so everything below is
read straight out of `reference/bn6f`.

THE STRUCT. `reference/bn6f/include/rom_structs/` has no `WaveData.inc` -- this disassembly
is asm-only and never grew C structs for the M4A sound engine's RAM-side types the way a
pret decomp would. So the 16-byte header below is the well-known M4A/MP2K `struct WaveData`
layout shared by every GBA game that uses Nintendo's stock sound engine (pokeemerald,
pokefirered, mother3, metroid zero mission, ... all agree on it byte for byte), cross-checked
against `byte_81597A0` itself rather than taken on faith:

    0x00  u16 type     -- 0 here; combined with `status` below, the whole 4-byte field
                          is zero, so whichever bit any convention uses for "this loops"
                          is unset. No separate loop flag exists anywhere else in the header.
    0x02  u16 status    -- 0 here (unused by the engine; always seen zero)
    0x04  u32 freq      -- sample rate in Hz, fixed point <<10 (i.e. Hz * 1024)
    0x08  u32 loopStart -- loop start point in samples; irrelevant when not looping
    0x0c  u32 size      -- PCM length in bytes (8-bit mono, so bytes == samples)
    0x10  s8  data[size]

VERIFIED, not assumed, three independent ways (`main()` below prints all three every run):
  1. freq = 0x00A44000 = 10,764,288; /1024 = 10512.0 Hz exactly -- matches the earlier
     research's "10512 Hz" and the fact that this is the mixer rate agb was tuned for.
  2. size = 0x00000759 = 1881 -- matches the earlier research's "1881 bytes", AND matches
     independently: the next labelled symbol after byte_81597A0 in dat37.s is byte_8159F0C
     (dat37.s:5205), 0x76C = 1900 bytes away, and 16 (header) + 1881 (data) = 1897, which
     rounds up to the next 4-byte boundary at exactly 1900. The size field and the file's own
     label spacing agree independently.
  3. type/status = 0x00000000 -- no loop bit set under any convention; loopStart = 0 is then
     moot. Consistent with the data shape too: the waveform fades to near-silence and its
     very last byte is exactly 0, which is what a one-shot foley hit (not a seamless loop)
     looks like.

SIGNED, NOT UNSIGNED. The GBA's DirectSound FIFO wants signed 8-bit PCM with a zero DC
level at 0x00, and that is what a `WaveData.data[]` stores natively: the sample's first two
bytes are 0x00, 0x03 and its last is 0x00 -- clustered around signed zero. Read the same
bytes as UNSIGNED (zero level 0x80) and the "silence" at both ends of the clip would instead
read as -128, i.e. the loudest possible negative rail -- which is exactly the "loud DC-offset
buzz" failure mode this file's caller warned about.

BUT THE WAV FORMAT ITSELF STORES 8-BIT PCM UNSIGNED (a WAV idiosyncrasy: every other bit
depth is signed, 8-bit is not). agb's `agb-sound-converter` (`vendor/agb/agb-sound-converter/
src/lib.rs`) loads WAVs through the `hound` crate, whose 8-bit read path is
`reader.read_u8().map(signed_from_u8)` (`hound-3.5.1/src/lib.rs`, `signed_from_u8(x) = x -
128`) -- i.e. hound assumes the WAV bytes are unsigned and converts them to signed before
agb-sound-converter re-casts them straight back to `u8` (`(sample >> 0) as u8` for 8-bit,
`agb-sound-converter/src/lib.rs:65`, which is a bit-preserving cast of a two's-complement
value, not a numeric conversion). So the round trip is transparent PROVIDED the WAV file
holds `gba_signed_byte + 128 (mod 256)` -- ordinary signed-to-unsigned 8-bit PCM conversion,
done below when writing the WAV. Writing the raw signed GBA bytes straight into the WAV's
data chunk (skipping this step) is precisely the bug that produces the buzz: hound would
subtract 128 a SECOND time.

AGB'S SUPPORTED RATES. `vendor/agb/agb/src/sound/mixer/mod.rs` defines `enum Frequency {
Hz10512, Hz18157, Hz32768 }` (lines ~138-144) with no other option and no resampling path in
`include_wav!` (`agb-sound-converter/src/lib.rs`) -- a WAV at any other rate is simply played
at the wrong pitch. 10512 is one of the three, and it is exactly this sample's native rate,
so this tool never resamples.

ALIASES. Only one is hardcoded, and its whole chain was re-derived and cross-checked against
`reference/bn6f`, not copied from the earlier research: `SOUND_HIT_6B` (SoundOffsets.inc:51,
value 0x6B) indexes the per-sound song table at dat37.s -- the table itself is commented with
running indices, and `// 0x358 (0x6B)` (dat37.s:4176-4177) reads `.word dword_81B8318,
0x00160016`. `dword_81B8318` (dat37.s:41523-41526) is a one-track M4A song header (`0xA00001`,
the same shape as SOUND_BUSTER_6A's `0x800001` immediately above it) whose voicegroup pointer
is `dword_8156D78` (dat37.s:2758-2761), a `ToneData` of type 0x08 (fixed-frequency DirectSound,
no PSG involved) whose wave pointer is `byte_81597A0` -- the WaveData this file exports by
default. The adjacency is itself corroborating: SOUND_BUSTER_6A (0x6A, dat37.s:4173-4174,
`dword_81B82FC` -> voicegroup `byte_8156D6C`, the confirmed PSG fire blip) sits in the very
next table slot before SOUND_HIT_6B's.

Output WAV: mono, 8-bit PCM (unsigned per the WAV spec), native sample rate, no metadata
chunks beyond the minimum `fmt `/`data` hound and Python's own `wave` module both read.
"""

import os
import re
import struct
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DATA_DIR = os.path.join(BN6, "data")
#: Where SOUND_HIT_6B's own WaveData lives; checked first since it is the common case.
DEFAULT_FILE = os.path.join(DATA_DIR, "dat37.s")

HEADER_FMT = "<HHIII"
HEADER_LEN = struct.calcsize(HEADER_FMT)  # 16

#: Symbol-name aliases for SOUND_* ids whose WaveData has been traced end to end.
#: See the module docstring for the full chain and its citations.
ALIASES = {
    "SOUND_HIT_6B": "byte_81597A0",
}

_LABEL_ADDR = re.compile(r"^[A-Za-z][A-Za-z0-9]*_([0-9A-Fa-f]{5,8})::")
_LABEL_ANY = re.compile(r"^([A-Za-z_][A-Za-z_0-9]*)::")


def symbol_address(symbol):
    """The address encoded in a `byte_XXXXXXX`-style label's own name.

    The disassembly's convention writes a symbol's own address as its hex suffix with
    any leading zero dropped (`byte_8156D6C` is ROM address 0x08156D6C) -- which needs no
    correction, since dropping a leading hex zero does not change the numeric value.
    """
    m = re.match(r"^[A-Za-z][A-Za-z0-9]*_([0-9A-Fa-f]{5,8})$", symbol)
    return int(m.group(1), 16) if m else None


def find_label_file(symbol, prefer=DEFAULT_FILE):
    """Which data/dat*.s file defines `symbol::`, checking `prefer` first."""
    candidates = [prefer] + sorted(
        p for p in (os.path.join(DATA_DIR, f) for f in os.listdir(DATA_DIR))
        if p != prefer and re.match(r"dat.*\.s$", os.path.basename(p))
    )
    needle = symbol + "::"
    for path in candidates:
        with open(path) as f:
            for line in f:
                if line.startswith(needle):
                    return path
    return None


def find_symbol_by_address(addr, prefer=DEFAULT_FILE):
    """The label in the data files whose own name encodes ROM address `addr`."""
    candidates = [prefer] + sorted(
        p for p in (os.path.join(DATA_DIR, f) for f in os.listdir(DATA_DIR))
        if p != prefer and re.match(r"dat.*\.s$", os.path.basename(p))
    )
    for path in candidates:
        with open(path) as f:
            for line in f:
                m = _LABEL_ADDR.match(line)
                if m and symbol_address(line[:line.index("::")]) == addr:
                    return line[:line.index("::")], path
    return None, None


def label_at(path, addr):
    """The label, if any, whose own name encodes exactly ROM address `addr`."""
    with open(path) as f:
        for line in f:
            m = _LABEL_ANY.match(line)
            if m and symbol_address(m.group(1)) == addr:
                return m.group(1)
    return None


def read_wave_data(symbol, path):
    """Parse a `WaveData` header at `symbol` in `path`, and its PCM.

    Returns (type_, status, freq_hz, loop_start, size, pcm_bytes_signed).
    """
    header = read_symbol(path, symbol, max_bytes=HEADER_LEN, through_labels=True)
    if len(header) < HEADER_LEN:
        raise SystemExit(f"{symbol}: only {len(header)} header bytes in {path}, need {HEADER_LEN}")
    type_, status, freq, loop_start, size = struct.unpack(HEADER_FMT, header)

    full = read_symbol(path, symbol, max_bytes=HEADER_LEN + size, through_labels=True)
    data = full[HEADER_LEN:HEADER_LEN + size]
    if len(data) != size:
        raise SystemExit(f"{symbol}: header says {size} PCM bytes, only found {len(data)} in {path}")

    if freq % 1024 != 0:
        print(f"WARNING: freq 0x{freq:08x} is not a whole multiple of 1024 Hz*1024 -- "
              f"{freq / 1024} Hz is not an integer", file=sys.stderr)
    if type_ != 0 or status != 0:
        print(f"WARNING: type=0x{type_:04x} status=0x{status:04x}, not the all-zero pattern this "
              f"tool has only ever verified against -- loop-flag assumption may not hold", file=sys.stderr)

    return type_, status, freq / 1024, loop_start, size, data


def write_wav(out_path, rate_hz, pcm_signed):
    """Write mono 8-bit PCM. WAV's 8-bit samples are UNSIGNED by spec (see module docstring)."""
    unsigned = bytes((b + 128) & 0xFF for b in pcm_signed)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(int(rate_hz))
        w.writeframes(unsigned)


def verify_wav(out_path):
    """Decode our own WAV back and report the numbers a DC-offset bug would show up in."""
    with wave.open(out_path, "rb") as w:
        assert w.getsampwidth() == 1 and w.getnchannels() == 1
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    # Undo the unsigned WAV convention the same way hound would, back to signed.
    signed = [b - 128 for b in raw]
    duration_ms = 1000.0 * len(signed) / rate
    peak = max(abs(s) for s in signed)
    mean = sum(signed) / len(signed)
    return dict(
        duration_ms=duration_ms, peak=peak, mean=mean,
        first16=signed[:16], last16=signed[-16:], rate=rate, n=len(signed),
    )


def resolve(arg):
    """`arg` -> (symbol, path). Accepts a known alias, a `byte_...`-style symbol, or an address."""
    arg = ALIASES.get(arg, arg)
    if re.match(r"^[A-Za-z_][A-Za-z_0-9]*$", arg) and not re.match(r"^0[xX]", arg):
        path = find_label_file(arg)
        if path is None:
            raise SystemExit(f"{arg}: no such label in {DATA_DIR}/dat*.s")
        return arg, path
    addr = int(arg, 0)
    symbol, path = find_symbol_by_address(addr)
    if symbol is None:
        raise SystemExit(f"0x{addr:08x}: no label in {DATA_DIR}/dat*.s encodes this address")
    return symbol, path


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    symbol, path = resolve(sys.argv[1])
    out_path = sys.argv[2] if len(sys.argv) > 2 else None

    type_, status, rate, loop_start, size, pcm = read_wave_data(symbol, path)
    rel = os.path.relpath(path, os.path.dirname(os.path.abspath(__file__)))
    print(f"{symbol} in {rel}:")
    print(f"  type=0x{type_:04x} status=0x{status:04x} freq={rate:.1f} Hz "
          f"loopStart={loop_start} size={size} bytes")

    here = symbol_address(symbol)
    expected = ((HEADER_LEN + size + 3) // 4) * 4
    if here is not None:
        end_label = label_at(path, here + expected)
        # Labels strictly between here and here+expected are known to be spurious --
        # the disassembler drops one wherever another reference lands mid-blob (the
        # same pattern chip_export.py documents for image blobs) -- so the meaningful
        # check is whether a label exists at exactly the end this header predicts,
        # not whether one exists sooner.
        if end_label is not None:
            print(f"  a label ({end_label}) exists exactly {expected} bytes on (16 + "
                  f"{size}, 4-aligned) -- confirms size independently of the header")
        else:
            print(f"  WARNING: no label exactly {expected} bytes on -- size is unconfirmed "
                  f"by address arithmetic", file=sys.stderr)

    print(f"  first 16 PCM bytes (signed): {list(struct.unpack_from('<16b', pcm, 0))}")
    print(f"  last 16 PCM bytes (signed):  {list(struct.unpack_from('<16b', pcm, len(pcm) - 16))}")

    if out_path is None:
        return
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    write_wav(out_path, rate, pcm)
    v = verify_wav(out_path)
    print(f"wrote {out_path}: {v['n']} samples at {v['rate']} Hz, {v['duration_ms']:.2f} ms")
    print(f"  peak={v['peak']} mean={v['mean']:.3f} "
          f"first16={v['first16']} last16={v['last16']}")
    if abs(v["mean"]) > 10:
        print("  WARNING: mean is far from zero -- likely a signed/unsigned conversion bug",
              file=sys.stderr)


if __name__ == "__main__":
    main()
