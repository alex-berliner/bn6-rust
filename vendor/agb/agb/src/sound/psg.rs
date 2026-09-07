//! # PSG: the GBA's four Game-Boy-compatible sound channels
//!
//! [`mixer`](super::mixer) drives DirectSound, a *software* mixer: it costs
//! CPU every single frame (agb's own docs put it at 6-10%) because every
//! sample of every playing wav has to be summed by hand. The four classic
//! Game Boy channels are the opposite: they are pure hardware. Write their
//! registers once and the APU keeps generating the waveform, sweeping the
//! frequency and running the volume envelope entirely on its own, with no
//! further work from the CPU and no per-frame call needed at all.
//!
//! This is a minimal driver, not a port of a music engine. It currently
//! exposes only channel 1 (the square wave with a hardware frequency sweep),
//! fired as a single one-shot note, in the style of
//! [`hw`](super::mixer)'s raw register access. There is no polyphony, no
//! software envelope and no note tracking -- every parameter here maps onto
//! one hardware register field, because that is all a one-shot square blip
//! needs.

use crate::memory_mapped::MemoryMapped;

// Channel 1 (square + sweep). Names follow the GBA I/O map rather than the
// classic Game Boy NRxx numbering, to match this crate's own house style
// (see `sound::mixer::hw`, which names its DirectSound registers the same
// way).
const SOUND1CNT_L: MemoryMapped<u16> = unsafe { MemoryMapped::new(0x0400_0060) };
const SOUND1CNT_H: MemoryMapped<u16> = unsafe { MemoryMapped::new(0x0400_0062) };
const SOUND1CNT_X: MemoryMapped<u16> = unsafe { MemoryMapped::new(0x0400_0064) };

// Shared across all four PSG channels. `SOUNDCNT_H` also carries
// DirectSound's own volume/enable/reset bits, which is exactly the register
// `mixer::hw::set_sound_control_register_for_mixer` writes wholesale -- so
// this module only ever touches it with a read-modify-write on the two PSG
// ratio bits, never a plain `set`, in case a game ends up using both.
const SOUNDCNT_L: MemoryMapped<u16> = unsafe { MemoryMapped::new(0x0400_0080) };
const SOUNDCNT_H: MemoryMapped<u16> = unsafe { MemoryMapped::new(0x0400_0082) };
const SOUNDCNT_X: MemoryMapped<u16> = unsafe { MemoryMapped::new(0x0400_0084) };

/// One of the four duty cycles a square channel (1 or 2) can generate.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum Duty {
    /// 12.5% high, 87.5% low: the thinnest, buzziest setting.
    Eighth,
    /// 25% high.
    Quarter,
    /// 50% high: a plain square wave.
    Half,
    /// 75% high (equivalent in timbre to 25%, inverted).
    ThreeQuarters,
}

impl Duty {
    const fn bits(self) -> u16 {
        match self {
            Duty::Eighth => 0,
            Duty::Quarter => 1,
            Duty::Half => 2,
            Duty::ThreeQuarters => 3,
        }
    }
}

/// A hardware frequency sweep, packed exactly as `SOUND1CNT_L` wants it.
/// `time` of 0 disables the sweep outright regardless of `shift`.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct Sweep {
    /// Time between sweep steps, in units of 1/128s (0-7; 0 = off).
    pub time: u8,
    /// `true` sweeps the frequency down over time, `false` sweeps it up.
    pub decreasing: bool,
    /// How large each step is: the register changes by `register >> shift`
    /// every `time`. 0-7.
    pub shift: u8,
}

impl Sweep {
    /// No sweep at all: a plain, unmoving pitch.
    pub const NONE: Sweep = Sweep { time: 0, decreasing: false, shift: 0 };

    const fn bits(self) -> u16 {
        ((self.time as u16 & 7) << 4) | ((self.decreasing as u16) << 3) | (self.shift as u16 & 7)
    }
}

/// The channel's volume envelope, packed as the high byte of
/// `SOUND1CNT_H`/`SOUND2CNT_H` wants it. Hardware steps `initial_volume`
/// (0-15) up or down by one every `period` 64ths of a second; `period` of 0
/// holds `initial_volume` forever (no envelope), and hitting 0 or 15 simply
/// stops moving rather than wrapping.
#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub struct Envelope {
    /// Starting volume, 0 (silent) to 15 (loudest).
    pub initial_volume: u8,
    /// `true` ramps volume up over time, `false` ramps it down.
    pub increasing: bool,
    /// Time between steps, in units of 1/64s (0-7; 0 = no envelope at all).
    pub period: u8,
}

impl Envelope {
    const fn bits(self) -> u16 {
        ((self.initial_volume as u16 & 0xf) << 12)
            | ((self.increasing as u16) << 11)
            | ((self.period as u16 & 7) << 8)
    }
}

/// Converts a frequency in Hz to the 11-bit value channel 1/2 use, per the
/// GBA's `frequency = 131072 / (2048 - register)` relationship. Out-of-range
/// requests clamp to the nearest representable end rather than panicking.
#[must_use]
pub fn hz_to_register(hz: u32) -> u16 {
    if hz == 0 {
        return 0;
    }
    let denom = 131072 / hz;
    if denom == 0 {
        0x7ff
    } else if denom >= 2048 {
        0
    } else {
        (2048 - denom) as u16 & 0x7ff
    }
}

/// Channel 1: a square wave with a hardware frequency sweep.
pub struct Channel1;

impl Channel1 {
    /// Fires a one-shot note. `frequency_register` is the raw 11-bit
    /// starting frequency (see [`hz_to_register`]); the sweep, if any, then
    /// moves it every frame or so entirely in hardware.
    ///
    /// `length_1_256s`, if given, tells the hardware to cut the channel dead
    /// after that many 1/256ths of a second, with no further CPU work at
    /// all. Pass `None` to leave the note running until its own envelope
    /// decays to (and holds at) zero -- which is how the original engine's
    /// square voices work when their "hardware time length control" byte is
    /// zero, i.e. disabled.
    pub fn play(
        sweep: Sweep,
        duty: Duty,
        envelope: Envelope,
        frequency_register: u16,
        length_1_256s: Option<u8>,
    ) {
        enable_psg_output();

        SOUND1CNT_L.set(sweep.bits());

        let (length_bits, length_enable) = match length_1_256s {
            Some(l) => (u16::from(64u8.saturating_sub(l)) & 0x3f, 1u16 << 14),
            None => (0, 0),
        };
        SOUND1CNT_H.set((duty.bits() << 6) | length_bits | envelope.bits());

        // Bit 15 (trigger/restart) must be written last, after every other
        // field is already in place, or the channel latches stale values.
        SOUND1CNT_X.set((frequency_register & 0x7ff) | length_enable | (1 << 15));
    }

    /// Silences the channel at once, by setting its envelope to volume zero
    /// with no step. `length_1_256s` is meant to do this in hardware and does
    /// not appear to: a note asking for 1/256 of a second still runs its
    /// envelope out in full under mGBA. So a caller that wants a note SHORTER
    /// than its envelope has to end it itself, which is what the original
    /// engine does anyway -- M4A runs its envelopes in software, which is why
    /// its blips are far shorter than the hardware's fastest decay.
    pub fn stop() {
        SOUND1CNT_H.set(SOUND1CNT_H.get() & 0x00ff);
        SOUND1CNT_X.set(SOUND1CNT_X.get() | (1 << 15));
    }
}

/// Turns on everything a PSG channel needs in order to be heard at all:
/// the master sound enable, channel 1 routed to both speakers, and the PSG
/// share of the DirectSound/PSG mix ratio at 100%. Idempotent, and cheap
/// enough to call before every note -- nothing here costs more than a
/// handful of register writes, done once per shot rather than once per
/// frame.
fn enable_psg_output() {
    // Master sound enable (bit 7 of SOUNDCNT_X, i.e. NR52).
    SOUNDCNT_X.set(SOUNDCNT_X.get() | (1 << 7));
    // Route channel 1 to both speakers (bits 8 and 12) at max shared PSG
    // master volume (bits 0-2 and 4-6). Channels 2-4's routing bits are left
    // exactly as they were.
    SOUNDCNT_L.set(SOUNDCNT_L.get() | 0x1177);
    // PSG output ratio is bits 0-1 of SOUNDCNT_H (2 = 100%); DirectSound's
    // own bits in the same register (2 and up) are read-modify-written
    // around, never overwritten.
    SOUNDCNT_H.set((SOUNDCNT_H.get() & !0b11) | 0b10);
}
