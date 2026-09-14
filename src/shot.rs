//! Travelling hitboxes that hop one panel at a time: the buster's shot and the
//! Mettaur's shockwave.
//!
//! bn6f models the shot as a temp attack object whose update state decrements
//! `Timer` and moves one panel once it drops below zero, so each hop costs two
//! frames (t3_0x0_80C4E58 -> sub_80C4E7C/sub_80C4F02, asm31.s:27728, 27769).
//! The shockwave is its own object that dwells 0x16 frames on each panel in
//! its first version and keeps going until the panel ahead is invalid
//! (t3_0x16_80C6B40, asm31.s:31354; byte_80C6B00, 31306).

use agb::display::GraphicsFrame;
use agb::display::Priority;
use agb::display::object::Object;

use crate::field;
use crate::spr;

/// Frames per hop for the buster: the timer is seeded from `Timer2 = 1` on
/// spawn (asm31.s:27728) and one decrement takes it to zero, the next past
/// it, so one panel every two frames.
const BUSTER_HOP: u8 = 2; // provenance: derived -- t3_0x0_80C4E58, asm31.s:27728
/// The shockwave's dwell per panel in its first version (byte_80C6B00).
const WAVE_HOP: u8 = 0x16; // provenance: derived -- byte_80C6B00, asm31.s:31306
/// Frames the panel a wave has left stays lit behind it. Measured against the
/// capture: two panels are lit for exactly three frames at every hop.
const LIGHT_LINGER: u8 = 3; // provenance: peeked -- measured against the capture

/// The buster shot's graphics live in the effect sprite list: byte_80B8BD4's
/// record selects `SpritePointersList` offset 0xc (`off_8031E00`) slot 2,
/// `sprite_82F569C` (data/SpritePointersList.s:88), whose animation 1 is the
/// small round bolt (the effect record at byte_80B8BD4 for the buster is
/// [0xC, 0x2, 0x1, 0x0, 0x0], so the shot plays anim 1, not the large orb of
/// anim 0). The shockwave's are `off_8031FA4` slot 3, `sprite_83536BC`,
/// animation 0 in its first version.
const ANIM: usize = 1; // provenance: derived -- byte_80B8BD4's own effect record, data/SpritePointersList.s:88

pub struct Shot {
    pub col: i32,
    pub row: i32,
    /// +1 travelling right, -1 left.
    pub dx: i32,
    ticks: u8,
    interval: u8,
    /// What the shots loop reads to land a hit. For the buster, cannon
    /// and Vulcan shots this is true on the update that just hopped the
    /// hitbox onto a new panel, so the hit lands on the hop frame itself.
    /// For the shockwave it is true on the update AFTER the hop: canon's
    /// new segment presents its collision during its own init tick
    /// (`sub_80C6B64`, asm31.s:31461-31496), which runs in the same frame
    /// the old segment's `sub_80C6C6A` spawns it, but the player's overlap
    /// test has already run by then, so the damage lands the next frame
    /// (F25c watch: PanelX reads (2,2) after canon frame 113, MegaMan's HP
    /// 60->50 after frame 114 -- flight 45, ours was 44). See `hop_pending`.
    hopped: bool,
    /// A shockwave hop the hit-check has not seen yet. Set on the hop
    /// frame, reported through `hopped` on the next update, so
    /// `just_hopped()` stays true one frame later for the shockwave only.
    // provenance: derived -- sub_80C6B64's init-tick present (asm31.s:31461-31496)
    // runs the same frame sub_80C6C6A hops (asm31.s:31570-31593); the hit lands
    // the frame after (F25c probe: arrival canon frame 113, HP drop 114).
    hop_pending: bool,
    /// Whether the hitbox keeps going after landing a hit.
    pub piercing: bool,
    /// Fired by the player, so it hits enemies; otherwise it hits the player.
    pub from_player: bool,
    pub damage: u16,
    /// Not drawn: the cannon's shot has no sprite of its own on the real
    /// ROM -- everything visible is the barrel object's animation -- so
    /// only its hitbox travels.
    pub hidden: bool,
    /// Vertical pixel offset from the panel centre, for shots that fan out
    /// (Vulcan's volley is spawned slightly above/below the row it is aimed
    /// at, sub_80EBF6E via dword_80EBFF0).
    pub y_offset: i32,
    /// The panel this shot has just left, and how many frames its light
    /// lingers there. The real ROM lights the new panel three frames before
    /// the old one goes out, so a moving wave shows two lit panels for three
    /// frames at every hop.
    pub left_panel: Option<(i32, i32)>,
    left_ticks: u8,
    /// Whether the panel this shot stands on lights up while it is there.
    /// The Mettaur's shockwave does: the real ROM paints the panel under it
    /// yellow for the whole 0x16 frames it dwells, and the light travels with
    /// it panel by panel.
    pub lights_panel: bool,
    /// Frames to sit on the spawn panel before moving, for a volley whose
    /// shots are released one after another (Vulcan fires every 0xa frames,
    /// sub_80EBF6E, so shot 1 goes at t=0, shot 2 at 0xa, shot 3 at 0x14).
    delay: u8,
    player: spr::Player,
    assets: spr::Assets,
    /// The segment left behind at the last hop, still playing out its own
    /// animation at the panel it departed from. A hop is not one sprite
    /// moving: `t3_0x16_80C6B40` (asm31.s:31354) spawns a whole new object on
    /// the next panel (`sub_80C6CE4`, asm31.s:31578) while the old one stays
    /// put and keeps looping until its own animation reports its last frame
    /// (`sub_80C6CBA`, asm31.s:31552-31567) -- there is no separate departure
    /// sprite or animation index, it is the same segment continuing to play
    /// whatever it was already showing. Independent of `left_panel`/
    /// `left_ticks`, which only linger the panel LIGHT for three frames; the
    /// visible fragments outlive that by several more.
    ///
    /// An `Option`, not a `Vec` -- tried, and measured WORSE on the same
    /// check (8725px over 20 of 70 frames, up from 460 over 4): this model
    /// dwells every panel `WAVE_HOP` (0x16) at `anim` 0 regardless of which
    /// hop it is, where the real ROM's `byte_80C6B00` shortens both the
    /// dwell and the animation for the later hops in a run (entries 12-15,
    /// asm31.s:31361-31366). A single fixed anim/dwell pair already makes
    /// one departure last close to its own dwell, so letting a second one
    /// start before the first ends compounds the mismatch across the whole
    /// attack instead of fixing the one hop this ticket measured. Newest
    /// wins; see `TRANSFER.md`.
    departure: Option<(spr::Player, (i32, i32))>,
}

impl Shot {
    pub fn buster(assets: spr::Assets, col: i32, row: i32, dx: i32, damage: u16) -> Self {
        Self::new(assets, col, row, dx, damage, BUSTER_HOP, false, true, 0, 0, ANIM)
    }

    /// The Cannon/HiCannon projectile: the big yellow-outlined white orb
    /// (byte_82FE704, anim 0 -- the static round orb the chip fires), which
    /// hops one panel a time like the buster. It is *not* the buster's small
    /// bolt; the Cannon chip fires this large orb.
    pub fn cannon(assets: spr::Assets, col: i32, row: i32, dx: i32, damage: u16) -> Self {
        let mut shot = Self::new(assets, col, row, dx, damage, BUSTER_HOP, false, true, 0, 0, 0);
        shot.hidden = true;
        shot
    }

    /// Vulcan's shot: the count and the vertical fan come from the caller,
    /// but the travel is the projectile's own -- one panel a frame, stopped
    /// by the first thing it hits (t3_0x12_80C6946 -> sub_80C6A08, asm31.s:
    /// 31212, 31215). `delay` holds it on the spawn panel the number of
    /// frames before the volley releases it.
    #[allow(clippy::too_many_arguments)]
    pub fn vulcan(
        assets: spr::Assets,
        col: i32,
        row: i32,
        dx: i32,
        damage: u16,
        y_offset: i32,
        delay: u8,
    ) -> Self {
        // Invisible in flight: t3_0x12 loads no sprite; only its hit spark
        // shows (sub_80C6A50, asm31.s:31253).
        let mut shot = Self::new(assets, col, row, dx, damage, 1, false, true, y_offset, delay, ANIM);
        shot.hidden = true;
        shot
    }

    pub fn shockwave(assets: spr::Assets, col: i32, row: i32, dx: i32, damage: u16) -> Self {
        let mut shot = Self::new(assets, col, row, dx, damage, WAVE_HOP, true, false, 0, 0, 0);
        // PRE-TICKED. Shots are stepped before the actors, so one the enemy
        // spawns during its own update misses this frame's tick and its
        // animation runs a frame behind the real ROM's for the whole flight.
        // Measured against the capture's Mettaur: with the wave shifted one
        // frame later, three of its four differing frames go to zero.
        shot.player.update();
        shot.lights_panel = true;
        shot
    }

    #[allow(clippy::too_many_arguments)]
    fn new(
        assets: spr::Assets,
        col: i32,
        row: i32,
        dx: i32,
        damage: u16,
        interval: u8,
        piercing: bool,
        from_player: bool,
        y_offset: i32,
        delay: u8,
        anim: usize,
    ) -> Self {
        Self {
            col,
            row,
            dx,
            ticks: interval,
            interval,
            piercing,
            from_player,
            damage,
            hidden: false,
            left_panel: None,
            left_ticks: 0,
            lights_panel: false,
            y_offset,
            delay,
            player: spr::Player::new(assets, anim),
            assets,
            departure: None,
            hopped: false,
            hop_pending: false,
        }
    }

    /// True when the hitbox arrived on its panel on the previous update --
    /// read AFTER `update()`, by the shots loop. For the buster, cannon
    /// and Vulcan shots that is the hop frame itself; for the shockwave it
    /// is the frame after, via the `hop_pending` latch (canon's hit lands
    /// the frame after the arrival: F25c probe, arrival 113, HP drop 114).
    /// A shot waiting out its release delay never reports a hop, so a
    /// delayed shot's first hit frame is unchanged.
    pub fn just_hopped(&self) -> bool {
        self.hopped
    }

    /// True on the frame the hitbox arrived on its panel, including the one
    /// it was spawned on, so a dwelling wave hits each panel once. A shot
    /// still waiting out its release delay has not arrived anywhere yet.
    pub fn just_arrived(&self) -> bool {
        self.delay == 0 && self.ticks == self.interval
    }

    /// Whether a one-shot leftover (the panel light's linger, or a departing
    /// segment still playing out) is keeping this shot alive after its own
    /// hitbox would otherwise be spent -- e.g. a wave that has just dwelt its
    /// way off the field.
    pub fn departing(&self) -> bool {
        self.left_panel.is_some() || self.departure.is_some()
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        if let Some((player, (col, row))) = &self.departure {
            let (px, py) = field::panel_centre(*col, *row);
            for part in player.parts().iter().rev() {
                let x = if self.dx < 0 {
                    -part.x - part.width
                } else {
                    part.x
                };
                Object::new(part.sprite.clone())
                    .set_priority(Priority::P2)
                    .set_pos((px + x, py + self.y_offset + part.y))
                    .set_hflip(part.hflip ^ (self.dx < 0))
                    .set_vflip(part.vflip)
                    .show(frame);
            }
        }
        if self.hidden {
            return;
        }
        let (px, py) = field::panel_centre(self.col, self.row);
        for part in self.player.parts().iter().rev() {
            let x = if self.dx < 0 {
                -part.x - part.width
            } else {
                part.x
            };
            Object::new(part.sprite.clone())
                .set_priority(Priority::P2)
                .set_pos((px + x, py + self.y_offset + part.y))
                .set_hflip(part.hflip ^ (self.dx < 0))
                .set_vflip(part.vflip)
                .show(frame);
        }
    }

    /// Advance one frame, hopping a panel whenever the timer runs out. Returns
    /// false once the shot leaves the field (col outside 1..=6) so the caller
    /// drops it; bn6f likewise destroys the shot when its panel goes invalid.
    pub fn update(&mut self) -> bool {
        self.player.update();
        // The segment departed at the previous hop, if any: check its OWN
        // animation before ticking it, matching `sub_80C6CBA`'s order
        // (asm31.s:31552-31567) -- read `sprite_getFrameParameters` first
        // and only call `object_updateSprite` on the frames it does not
        // vanish.
        if let Some((player, _)) = &mut self.departure {
            let was_last = player.on_last_frame();
            player.update();
            if was_last && player.frame_key().1 == 0 {
                self.departure = None;
            }
        }
        // The shockwave's hop becomes hittable one frame later (see
        // `hop_pending`): report last frame's hop, then clear the latch.
        // Every other shot reports the hop itself, as before.
        if self.lights_panel {
            self.hopped = self.hop_pending;
            self.hop_pending = false;
        } else {
            self.hopped = false;
        }
        if self.delay > 0 {
            self.delay -= 1;
            return true;
        }
        if self.left_ticks > 0 {
            self.left_ticks -= 1;
            if self.left_ticks == 0 {
                self.left_panel = None;
            }
        }
        self.ticks -= 1;
        if self.ticks == 0 {
            if self.lights_panel {
                self.hop_pending = true;
            } else {
                self.hopped = true;
            }
            if self.lights_panel {
                self.left_panel = Some((self.col, self.row));
                self.left_ticks = LIGHT_LINGER;
                // The old segment stays at the panel it is leaving and keeps
                // playing what it was already showing; the continuing shot
                // gets a fresh one, as `sub_80C6B64` (asm31.s:31389) does for
                // the new segment it spawns on the next panel.
                let anim = self.player.anim();
                let old = core::mem::replace(&mut self.player, spr::Player::new(self.assets, anim));
                // PRE-TICKED, exactly as the launched segment is in
                // `shockwave()`: the segment a hop spawns runs its own init
                // AND one `object_updateSprite` in the SAME frame the old one
                // hops. `t3_0x16_80C6B40` (asm31.s:31413-31421) dispatches on
                // CurState -- state 0 is `sub_80C6B64` (off_80C6B58,
                // asm31.s:31425-31428), which loads the sprite and the
                // animation (asm31.s:31456-31466) -- and then falls through to
                // `bl object_updateSprite` (asm31.s:31420) on that very frame,
                // so the new segment's first animation frame is DISPLAYED on
                // the hop frame and its duration counts that frame. Without
                // this tick `Player::new`'s `fresh` flag eats the next update
                // and every frame of the segment's animation lands one frame
                // late (F25d, measured: canon's anim-frame changes at hop+5,
                // +10, +15, +21 -- assets/wave.bin anim 0 durations 5,5,5,6,5
                // -- ours at +6, +11, +16, +22, and the departing segment
                // vanished at hop+5 instead of hop+4).
                // provenance: derived -- t3_0x16_80C6B40's post-dispatch
                // object_updateSprite, asm31.s:31413-31421.
                self.player.update();
                self.departure = Some((old, (self.col, self.row)));
            }
            self.col += self.dx;
            self.ticks = self.interval;
        }
        (1..=field::COLS).contains(&self.col)
    }
}
