// The learn feed's slides, in order. Editing this file is how you add,
// remove or reword a slide -- learn.html renders whatever is in this array
// and needs no other change.
//
// Each slide is:
//   title     short, plain, no puns
//   image     path relative to web/ (learn.html lives in web/). Optional:
//             leave it out and the slide renders with no picture at all.
//   imageAlt  what the picture shows, for a reader who cannot see it
//   codePath  where the snippet came from, shown above the code
//   code      a REAL excerpt from src/ at the time it was written, trimmed;
//             keep it to about 18 lines, and never wrap a line by hand --
//             the page scrolls code sideways. A "// ..." line marks
//             something left out; say in the text what it was.
//   text      about 60-100 words of plain English: how this part works, as
//             it works today. No jargon the same slide does not explain.

var SLIDES = [

{
  title: "What happens in one frame",
  codePath: "src/main.rs",
  code: `let fixture = fixture::read();

// ... the battle is built from that, and then this runs once per frame:
loop {
    input.update();
    rng.next();
    let over = battle.update(&input, &gfx, &mut mixer);
    if over {
        break;
    }
    let mut frame = gfx.frame();
    battle.draw(&mut frame);
    mixer.frame();
    frame.commit();
}`,
  text: "The whole game is this loop. Read the buttons, step the shuffling number generator so every battle deals a different folder, advance the fight by exactly one frame, then draw the new picture and hand it over. The last call waits for the screen to finish its refresh, which is what paces the loop at sixty frames a second. Before any of it, the game looks at a small block of numbers left in memory: if one is there it describes the scene to set up, and if not the game starts an ordinary fight of its own.",
},

{
  title: "The field is eighteen panels",
  codePath: "src/field.rs",
  code: `pub const COLS: i32 = 6;
pub const ROWS: i32 = 3;

/// Screen position of the centre of a panel, for 1-based \`(col, row)\`.
pub fn panel_centre(col: i32, row: i32) -> (i32, i32) {
    (col * 40 - 20, row * 24 + 60)
}

/// The half of the field a side owns. Columns 1-3 are the player's, 4-6 the
/// enemy's; a navi cannot leave its own half without a chip that grabs area.
pub fn half(enemy_side: bool) -> (i32, i32) {
    if enemy_side { (4, COLS) } else { (1, 3) }
}`,
  text: "Three rows, six columns, numbered from one. Columns one to three are yours, four to six the enemy's, and who owns each panel is stored per panel so a chip can steal one. Almost nothing in the code thinks in pixels: MegaMan, an enemy, a shot and a panel highlight all carry a column and a row. One short function turns that pair into the pixel at the middle of the panel, forty across and twenty-four down apiece. Moving is changing two small numbers, and everything that draws asks the same function where that is.",
},

{
  title: "One slot for what MegaMan is doing",
  codePath: "src/actor.rs",
  code: `pub fn take_damage(&mut self, amount: u16) -> bool {
    if self.invulnerable > 0 || self.invisible > 0 {
        return false;
    }
    // ... a barrier soaks the hit here instead
    self.hp = self.hp.saturating_sub(amount);
    self.hits_taken = self.hits_taken.saturating_add(1);
    self.invulnerable = self.mercy;
    self.flash = FLASH_FRAMES;
    self.player.set_white(true);

// ... and while that counter runs down, the body is skipped on the frames
// where its second bit is set: two hidden, two shown, over and over.
if !dying && self.flash == 0 && self.invulnerable > 0 && (self.invulnerable >> 1) & 1 != 0 {
    return;
}`,
  text: "MegaMan holds one job at a time: standing, hopping to another panel, winding up, swinging, reeling from a hit, or being deleted. Each one carries its own countdown, and when that reaches zero the job goes back to standing, so nothing can start while something else is running. A hit that lands sets his health, flashes him white for a few frames, and starts a second counter. While that counter runs he cannot be hit again, and he is skipped on two frames out of every four, which is the blinking you see.",
},

{
  title: "How a shot lands",
  codePath: "src/shot.rs and src/battle.rs",
  code: `// src/shot.rs -- the hitbox's own clock: one panel when it runs out.
self.ticks -= 1;
if self.ticks == 0 {
    // ... a shockwave also lights the panel it is leaving
    self.col += self.dx;
    self.ticks = self.interval;
}

// src/battle.rs -- whoever stands where it arrived takes the damage.
let arrived = spawn_arrival || self.shots[i].just_hopped();
if !spent && arrived {
    let at = (self.shots[i].col, self.shots[i].row);
    if self.shots[i].from_player {
        for enemy in self.enemies.iter_mut().filter(|e| e.is_targetable()) {
            if enemy.panel() == at {
                enemy.take_damage(self.shots[i].damage);
    // ... the same test against MegaMan for an enemy's shot, then:
    spent = hit && !self.shots[i].piercing;`,
  text: "A shot is not a moving picture with a box around it. It is a panel, a direction and a countdown: every frame the countdown drops by one, and at zero the shot steps one column and starts over, so the buster's bolt crosses a panel every two frames and a shockwave dwells twenty-two. On the frame it arrives, anything standing on that panel takes its damage. Yours hit enemies, an enemy's hits you, and unless the shot pierces it is spent on the first thing it touches.",
},

{
  title: "The Mettaur's routine",
  codePath: "src/ai.rs",
  code: `self.mettaur = match self.mettaur {
    MettaurState::RowCheck => {
        let (_, row) = me.panel();
        if self.param4 == 0 {
            self.param4 = SPAWN_FRAMES as u8;
            MettaurState::Spawn(SPAWN_FRAMES)
        } else if row != target.1 {
            me.hop(0, (target.1 - row).signum(), blocked);
            MettaurState::AlignHop
        } else {
            MettaurState::Decide
        }
    }
    MettaurState::AlignHop => MettaurState::RowCheck,
    MettaurState::Decide => {
        me.attack(actor::SWING);
        MettaurState::RowCheck
    }`,
  text: "The Mettaur runs a tiny loop, and only when it is not already busy. It waits about thirty frames after appearing. Then it compares its row with yours: different, and it hops one panel toward you and waits for the hop to finish before looking again; the same, and it swings. The swing pose holds for sixty-four frames, the shockwave is launched partway through it, and forty frames of recovery follow before the loop starts over. Two branches for a confused Mettaur are left out above, because nothing in this game confuses one yet.",
},

{
  title: "How an animation plays",
  codePath: "src/spr.rs",
  code: `pub struct Frame {
    pub gfx: u16,
    pub pal: u16,
    pub oam_first: u16,
    pub oam_count: u16,
    pub duration: u8,
    /// 0x80 marks the last frame, 0x40 that the animation restarts after it.
    pub flags: u8,
}
pub fn update(&mut self) {
    self.ticks_left = self.ticks_left.saturating_sub(1);
    if self.ticks_left > 0 {
        return;
    }
    // ... the test for "this was the last frame" goes here
    self.frame_in_anim = (self.frame_in_anim + 1) % count;
    self.load_frame();
}`,
  text: "Every character's artwork is pulled out of the original game into one file: a list of animations, each a run of frames, each frame naming its pixels, its colours, how many frames to hold, and the handful of pieces it is built from with their offsets and flips. Playing one is a countdown. Each frame subtract one; while it is above zero nothing changes at all, which is why the picture is rebuilt only when it actually moves. At zero, step to the next frame and load its pieces. A one-shot animation stops on its last frame and waits.",
},

{
  title: "The custom screen and the gauge",
  codePath: "src/battle.rs and src/custom.rs",
  code: `// src/battle.rs -- 0xd of 0x4000 a frame; full, and the window is due.
self.gauge = (self.gauge + GAUGE_STEP).min(GAUGE_FULL);
if self.gauge == GAUGE_FULL && self.open_window_allowed() {
    self.gauge_pause = GAUGE_PAUSE;
}

// src/custom.rs -- it scrolls in from 0x78 to 0, 0xc of it a frame.
const SLIDE_FROM: i32 = 0x78;
const SLIDE_STEP: i32 = 0xc;
Phase::Opening { x } if x > SCROLL_OPEN => {
    let x = (x - SLIDE_STEP).max(SCROLL_OPEN);
    bg.set_scroll_pos((x, SCROLL_Y));
    self.reveal(bg, x);
    if x == SCROLL_OPEN { Phase::Open } else { Phase::Opening { x } }
}
// ... and a chip can only join four others already picked:
if self.picks.len() >= HAND_SIZE {
    return false;`,
  text: "The gauge is one number that grows by a fixed step every frame until it hits its top. That is the whole trigger: at the top the fight pauses for the chimes, then the window scrolls in from a hundred and twenty pixels away, twelve a frame, so it takes ten frames, revealing more of itself with every step. Inside, a cursor walks the five offered chips. One may join your hand of five if it shares a name or a code with what you have picked. Leaving empties the gauge and the picks become the hand.",
},

{
  title: "The HUD and the background",
  codePath: "src/hud.rs and src/backdrop.rs",
  code: `// src/hud.rs -- a number on screen walks toward the value it should show.
let step = self.shown.abs_diff(actual) / 8 + 4;
self.shown = if actual < self.shown {
    self.shown.saturating_sub(step).max(actual)
} else {
    (self.shown + step).min(actual)
};
// src/backdrop.rs -- two counters slide the pattern, a third steps its art.
const SCROLL_X_Q: u32 = 2;
const SCROLL_Y_Q: u32 = 1;
pub fn update(&mut self, gfx: &Graphics) {
    self.timer -= 1;
    if self.timer == 0 {
        self.entry = (self.entry + 1) % STEP_ORDER.len();
        self.timer = STEP_HOLD[self.entry];
        self.show_step(gfx, STEP_ORDER[self.entry]);
    }
    self.x_q = (self.x_q + SCROLL_X_Q) % (256 * 4);`,
  text: "Every frame the same stack is painted: the moving pattern at the back, the field over it, then the boxes, gauge and numbers on top. A health number never jumps to its new value. It walks, an eighth of the gap plus four each frame, and the digits wear a different colour set while it moves, so a big hit rolls down over several frames. Behind all of it the pattern slides half a pixel across and a quarter down every frame, while a separate schedule of twenty-nine entries swaps which artwork its squares are showing.",
},

];
