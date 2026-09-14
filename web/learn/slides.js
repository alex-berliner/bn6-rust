// The learn feed's slides, in order. Editing this file is how you add,
// remove or reword a slide -- learn.html renders whatever is in this array
// and needs no other change.
//
// Each slide is:
//   title     short, plain, no puns
//   image     path relative to web/ (learn.html lives in web/)
//   imageAlt  what the picture shows, for a reader who cannot see it
//   codePath  where the snippet came from, shown above the code
//   code      a REAL excerpt from src/ at the time it was written, trimmed;
//             keep it to about 18 lines, and never wrap a line by hand --
//             the page scrolls code sideways
//   text      about 60-100 words, one idea, ending with why it mattered.
//             Plain words only: no jargon from this project that the same
//             slide does not explain.

var SLIDES = [

{
  title: "How we tell our game what scene to show",
  image: "captures/field-progress.gif",
  imageAlt: "Three stacked strips of the same battle: the real game on top, our version before the fix in the middle, our version after the fix at the bottom.",
  codePath: "src/fixture.rs",
  code: `// The test writes these 64 bytes into memory before the game starts.
pub const ADDR: usize = 0x0200_0040;

pub struct Fixture {
    pub enemies: u8,
    pub enemy_kind: u8,
    pub enemy_col: u8,
    pub enemy_row: u8,
    pub megaman_hp: u16,
    pub hand_count: u8,
    pub hand: [u8; 5],
    pub gauge: u8,
    pub flags: u8,
    pub scroll_xq: u16,
    pub scroll_yq: u16,
    // ... and twenty more fields
}`,
  text: "Our game boots straight into a fight it picks for itself. To match one moment from the real game, the test has to set the scene first: one Mettaur, on that panel, this much health, these chips in hand, the gauge this full. It writes those numbers into a fixed place in the machine's memory before the game starts, and the game reads them once, on its very first frame. That is why one copy of our game covers every test scene. A new scene is a new list of numbers, not a new build.",
},

{
  title: "How a comparison works, and why a wrong answer must fail",
  image: "captures/windowclose-f29-progress.gif",
  imageAlt: "Three stacked strips of the chip window closing: the real game on top, our version before the fix in the middle, our version after the fix at the bottom.",
  codePath: "src/main.rs",
  code: `// "BATT" as a number: our game leaves it in memory once a fight runs.
const BATTLE_MAGIC: u32 = 0x4241_5454;

fn write_battle_marker(magic: u32, frame: u32) {
    unsafe {
        let p = core::ptr::addr_of_mut!(BATTLE_MARKER) as *mut u32;
        core::ptr::write_volatile(p, magic);
        core::ptr::write_volatile(p.add(1), frame);
    }
}

// ... in the main loop, once per frame:
if clocks_visible {
    write_battle_marker(BATTLE_MAGIC, battle_frame);
    battle_frame += 1;
}`,
  text: "Two runs of the same fight do not line up by themselves: our game and the real one take different amounts of time to reach the first frame of battle. So ours leaves a word in memory reading BATT once the fight starts, next to a count of battle frames. The test that compares our screen with the real game's, pixel by pixel, uses that word to find frame one on each side. Then it repeats the comparison against a copy of our own screen nudged sideways: if that also reports zero, the comparison is blind and does not count.",
},

{
  title: "A shockwave segment that started one frame late",
  image: "captures/mettaur-f25d-progress.gif",
  imageAlt: "Three stacked strips of a Mettaur shockwave crossing the field: the real game on top, our version before the fix in the middle, our version after the fix at the bottom.",
  codePath: "src/shot.rs",
  code: `self.ticks -= 1;
if self.ticks == 0 {
    if self.lights_panel {
        self.hop_pending = true;
    } else {
        self.hopped = true;
    }
    if self.lights_panel {
        self.left_panel = Some((self.col, self.row));
        self.left_ticks = LIGHT_LINGER;
        let anim = self.player.anim();
        let old = core::mem::replace(&mut self.player, spr::Player::new(self.assets, anim));
        // The new segment plays one animation step on the frame it is born.
        self.player.update();
        self.departure = Some((old, (self.col, self.row)));
    }`,
  text: "A shockwave crosses the field as a chain of segments: each hop leaves the old one standing and starts a fresh one on the next panel. Ours was 4265 pixels away from the real game, and every one of them sat on eight frames: exactly the frames where a segment changed its picture or disappeared, always a frame late. Our fresh segment was made with its picture marked as not yet drawn, so it slept through its first step. The real game draws it the moment it is born. One added line, and all 70 frames read zero.",
},

{
  title: "The HUD is a checklist of elements",
  image: "captures/popup-f27b-progress.gif",
  imageAlt: "Three stacked strips of a damage number popping up over a Mettaur: the real game on top, our version before the fix in the middle, our version after the fix at the bottom.",
  codePath: "src/battle.rs",
  code: `// The real game keeps one switch per piece of the HUD.
if over {
    self.hud_live = false;
}

// ... and when drawing, the face in the blue frame asks that switch:
if self.hud_live && self.shown.is_none() && self.fade_out == 0 {
    self.emotion
        .show(frame, self.custom.as_ref().map_or(0, |c| c.hud_obj_x()));
}`,
  text: "The face in the blue frame at the top left is not tied to the enemy, but we hid it the instant the last Mettaur died. The real game keeps a list of switches, one for each piece of the display around the fight, and the face's switch stays on for another 47 frames, right through the death and the dissolve, until the end-of-battle sequence turns five pieces off at once. Watching that moment on a snapshot of the real game gave us the exact frame. Matching it took this comparison from 60614 differing pixels to 5094.",
},

{
  title: "The moving background has a clock",
  image: "captures/windowclose-f26b-progress.gif",
  imageAlt: "Three stacked strips of a battle with the chip window sliding shut: the real game on top, our version before the fix in the middle, our version after the fix at the bottom.",
  codePath: "src/backdrop.rs",
  code: `/// Quarter-pixels of scroll per frame, across and down.
const SCROLL_X_Q: u32 = 2;
const SCROLL_Y_Q: u32 = 1;

const STEP_ORDER: [u16; 29] = [
    2, 1, 2, 1, 2, 1, 2, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 4, 5, 6, 0, 1,
];
const STEP_HOLD: [u16; 29] = [
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
];
pub fn update(&mut self, gfx: &Graphics) {
    self.timer -= 1;
    if self.timer == 0 {
        self.entry = (self.entry + 1) % STEP_ORDER.len();
        self.timer = STEP_HOLD[self.entry];
        self.show_step(gfx, STEP_ORDER[self.entry]);
    }
    self.x_q = (self.x_q + SCROLL_X_Q) % (256 * 4);`,
  text: "The pattern behind a fight never sits still: it slides left and up every frame, and the squares themselves swap artwork on a separate timetable. Both clocks start with the battle, and a snapshot of the real game is thousands of frames in, so both are mid-cycle. Until each test scene began at the same two counter values, the backgrounds sat a fixed distance apart on every frame. The real game's counters fall by 8 and 4 a frame; ours count the same motion in quarter pixels. Starting them together took this comparison from 407778 differing pixels to 34707.",
},

{
  title: "The custom gauge's stripes",
  image: "captures/tiles-progress.gif",
  imageAlt: "Three stacked strips of the custom gauge along the top of the screen: the real game on top, our version before the fix in the middle, our version after the fix at the bottom.",
  codePath: "src/hudtiles.rs",
  code: `const BAR_FRAMES: u32 = 7;

// One counter drives both: stripe = counter / 7, marker colour = one bit.
if ready {
    self.gauge_tick = self.gauge_tick.wrapping_add(1);
} else {
    self.gauge_tick = 0;
}
let full_state: Option<(u16, u16)> = if ready {
    Some((
        BAR_CYCLE[((self.gauge_tick / BAR_FRAMES) % BAR_CYCLE.len() as u32) as usize],
        if self.gauge_tick & 8 != 0 {
            MARKER_READY
        } else {
            MARKER_WAITING
        },
    ))`,
  text: "When the custom gauge fills, its stripes start flowing and the marker at the end changes colour. We had matched that by eye with three fitted numbers that were close but never right. The real game runs it off one counter that ticks up for as long as the gauge is full: the stripe picture is that counter divided by 7, and the marker's colour is one bit of the same counter. Copying the real rule took this comparison from 538 differing pixels to 208, and those last 208 turned out to be the background, not the gauge.",
},

];
