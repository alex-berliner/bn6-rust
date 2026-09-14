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
//   highlights 3 to 5 {code, text} pairs. Each is an EXACT substring of this
//             slide's own `code` and `text`, and each must occur exactly
//             once in its string -- lengthen the substring or reword the
//             sentence if it does not. The first pair gets colour 1, the
//             second colour 2, and so on up to 5; the code half and the
//             text half are painted the same colour and light up together
//             when either is hovered or tapped. Point them at the concrete
//             things (a counter, a hop, the gauge), not whole sentences.
//             A substring the page cannot find is skipped with a warning in
//             the browser console, so check there after editing.
//
// NUMBERS. Any number a slide shows -- in an added comment or in the words --
// is explained on that slide: what it counts, its decimal value if it is
// written in hex, and a human unit where one helps (frames at sixty a second,
// pixels, panels). A bare "0xd of 0x4000" is not allowed; "13 a frame up to
// 16384, about 21 seconds" is.
//
// The page remembers which slide the reader was on (localStorage "learn.pos",
// falling back to a cookie), so inserting a slide shifts where a returning
// reader lands. The "start over" control in the dots clears it.

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
  highlights: [
    { code: "let fixture = fixture::read();",
      text: "a small block of numbers left in memory" },
    { code: "input.update();",
      text: "Read the buttons" },
    { code: "rng.next();",
      text: "step the shuffling number generator" },
    { code: "battle.update(&input, &gfx, &mut mixer)",
      text: "advance the fight by exactly one frame" },
    { code: "frame.commit();",
      text: "waits for the screen to finish its refresh" },
  ],
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
  highlights: [
    { code: "pub const COLS: i32 = 6;\npub const ROWS: i32 = 3;",
      text: "Three rows, six columns" },
    { code: "pub fn panel_centre(col: i32, row: i32) -> (i32, i32)",
      text: "One short function turns that pair into the pixel at the middle of the panel" },
    { code: "(col * 40 - 20, row * 24 + 60)",
      text: "forty across and twenty-four down apiece" },
    { code: "if enemy_side { (4, COLS) } else { (1, 3) }",
      text: "Columns one to three are yours, four to six the enemy's" },
  ],
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
  highlights: [
    { code: "if self.invulnerable > 0 || self.invisible > 0 {",
      text: "he cannot be hit again" },
    { code: "self.hp = self.hp.saturating_sub(amount);",
      text: "sets his health" },
    { code: "self.invulnerable = self.mercy;",
      text: "starts a second counter" },
    { code: "self.player.set_white(true);",
      text: "flashes him white for a few frames" },
    { code: "(self.invulnerable >> 1) & 1 != 0",
      text: "skipped on two frames out of every four" },
  ],
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
  highlights: [
    { code: "self.ticks -= 1;",
      text: "every frame the countdown drops by one" },
    { code: "self.col += self.dx;",
      text: "the shot steps one column" },
    { code: "self.ticks = self.interval;",
      text: "starts over" },
    { code: "enemy.take_damage(self.shots[i].damage);",
      text: "anything standing on that panel takes its damage" },
    { code: "spent = hit && !self.shots[i].piercing;",
      text: "unless the shot pierces it is spent on the first thing it touches" },
  ],
},

{
  title: "The Mettaur's routine",
  codePath: "src/objects.rs",
  code: `match self.decide {
    METTAUR_ROW => {
        let (_, row) = me.panel();
        // ... the once-only spawn pause is the first branch here, then:
        } else if row != target.1 {
            self.hop_done = me.hop(0, (target.1 - row).signum(), blocked) as u8;
            self.decide = METTAUR_ALIGN;
        } else {
            self.decide = METTAUR_DECIDE;
    METTAUR_ALIGN => {
        self.decide = if self.hop_done != 0 {
            METTAUR_ROW
        } else {
            METTAUR_DECIDE
        };
    }
    METTAUR_DECIDE => {
        me.attack(actor::SWING);`,
  text: "The Mettaur runs a tiny loop with four named places, and only while it is not already busy. Compare its row with yours. Different, and it asks for a hop one panel toward you and moves to the waiting place; when the hop reports back it starts over, and if the hop was refused it attacks from where it stands. Same row, and it swings straight away. The swing pose holds 64 frames, just over a second, with 40 more of recovery, and the shockwave leaves partway through.",
  highlights: [
    { code: "let (_, row) = me.panel();",
      text: "Compare its row with yours" },
    { code: "} else if row != target.1 {",
      text: "Different, and it asks for a hop one panel toward you" },
    { code: "self.decide = METTAUR_ALIGN;",
      text: "moves to the waiting place" },
    { code: "self.decide = if self.hop_done != 0 {",
      text: "when the hop reports back it starts over, and if the hop was refused it attacks from where it stands" },
    { code: "me.attack(actor::SWING);",
      text: "Same row, and it swings straight away" },
  ],
},

{
  title: "How an animation plays",
  codePath: "src/spr.rs",
  code: `// Two flag bits on a command: 0x80 (128) means "last one", 0x40 (64)
// means "start the animation over after it".
pub fn update(&mut self) {
    loop {
        if self.countdown == 0 {
            self.countdown = 0xFF;
        } else {
            self.countdown -= 1;
            return;
        }
        let (first, count) = self.assets.anim(self.anim);
        if self.cmd_flags & CMD_END == 0 && self.frame_in_anim + 1 < count {
            self.step_stream(first);
            self.load_frame();
            continue;
        }
        if self.cmd_flags & CMD_LOOP != 0 {
            self.bind(self.anim);`,
  text: "An animation is a list of commands, and each command says which picture to show, how many frames to hold it, and two flag bits. Playing it is one countdown. Every frame it drops by one, and while it is still above zero nothing at all is rebuilt. When it runs out the current command is consumed: move to the next one and load it, or, if this was the last, either start the whole list again or hold this picture. The 128 bit marks the last command, the 64 bit asks for the restart.",
  highlights: [
    { code: "self.countdown -= 1;",
      text: "Every frame it drops by one" },
    { code: "return;",
      text: "while it is still above zero nothing at all is rebuilt" },
    { code: "self.step_stream(first);",
      text: "move to the next one and load it" },
    { code: "if self.cmd_flags & CMD_END == 0 && self.frame_in_anim + 1 < count {",
      text: "The 128 bit marks the last command" },
    { code: "if self.cmd_flags & CMD_LOOP != 0 {",
      text: "the 64 bit asks for the restart" },
  ],
},

{
  title: "The custom screen and the gauge",
  codePath: "src/battle.rs and src/custom.rs",
  code: `// src/battle.rs -- the gauge grows by 13 a frame; at 16384 (about 21 seconds) it is full and the window may open.
self.gauge = (self.gauge + GAUGE_STEP).min(GAUGE_FULL);
if self.gauge == GAUGE_FULL && self.open_window_allowed() {
    self.gauge_pause = GAUGE_PAUSE;
}

// src/custom.rs -- the window starts 120 pixels off screen and slides 12 a frame: ten frames to arrive.
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
  highlights: [
    { code: "self.gauge = (self.gauge + GAUGE_STEP).min(GAUGE_FULL);",
      text: "one number that grows by a fixed step every frame until it hits its top" },
    { code: "self.gauge_pause = GAUGE_PAUSE;",
      text: "the fight pauses for the chimes" },
    { code: "const SLIDE_FROM: i32 = 0x78;",
      text: "from a hundred and twenty pixels away" },
    { code: "const SLIDE_STEP: i32 = 0xc;",
      text: "twelve a frame" },
    { code: "if self.picks.len() >= HAND_SIZE {",
      text: "your hand of five" },
  ],
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
  highlights: [
    { code: "let step = self.shown.abs_diff(actual) / 8 + 4;",
      text: "an eighth of the gap plus four each frame" },
    { code: "self.shown = if actual < self.shown {",
      text: "A health number never jumps to its new value" },
    { code: "const SCROLL_X_Q: u32 = 2;\nconst SCROLL_Y_Q: u32 = 1;",
      text: "half a pixel across and a quarter down every frame" },
    { code: "self.entry = (self.entry + 1) % STEP_ORDER.len();",
      text: "a separate schedule of twenty-nine entries" },
    { code: "self.show_step(gfx, STEP_ORDER[self.entry]);",
      text: "swaps which artwork its squares are showing" },
  ],
},

{
  title: "Every object gets its turn",
  codePath: "src/objects.rs",
  code: `pub fn battle_common_path(actor: &mut Actor) -> Update {
    actor.update()
}
// The thinking leg: the enemy picks what to do next.
pub fn enemy_think(
    ai: &mut Ai,
    me: &mut Actor,
    target: (i32, i32),
    blocked: u32,
    rng: &mut Rng,
) {
    // ... one arm per kind of enemy, all reaching the same call
    ai.update(me, target, blocked, rng);
}
// The acting leg: what it picked now happens, down the shared path.
pub fn enemy_act(enemy: &mut Actor) -> Update {
    battle_common_path(enemy)
}`,
  text: "The original game keeps one list of everything alive in a battle and, every frame, hands each entry to the routine for its kind. This file is that list. An enemy goes through in two legs: a thinking leg that picks a move, then an acting leg that carries it out, and both end in one shared routine every object on the field runs. MegaMan and each travelling shot have their own way in to the same shape. Naming the legs puts the order of a whole frame in one file instead of scattered loops.",
  highlights: [
    { code: "pub fn battle_common_path(actor: &mut Actor) -> Update {",
      text: "one shared routine every object on the field runs" },
    { code: "pub fn enemy_think(",
      text: "a thinking leg that picks a move" },
    { code: "pub fn enemy_act(enemy: &mut Actor) -> Update {",
      text: "an acting leg that carries it out" },
    { code: "ai.update(me, target, blocked, rng);",
      text: "hands each entry to the routine for its kind" },
  ],
},

{
  title: "The Mettaur waits before its first move",
  codePath: "src/objects.rs",
  code: `// 0x1e is 30, and the wait lasts 31 frames -- about half a second.
const METTAUR_SPAWN_WAIT: u16 = 0x1e;

// The counter is read after the subtraction, so a stored 30 covers 31 frames.
if self.cur_action == METTAUR_ACT_WAIT {
    if self.wait > 0 {
        self.wait -= 1;
    } else {
        self.cur_action = METTAUR_ACT_DECIDE;
    }
    return;
}
// ... and the very first time its decision loop runs, it arms that wait:
self.param4 = METTAUR_SPAWN_WAIT as u8;
self.wait = METTAUR_SPAWN_WAIT;
self.cur_action = METTAUR_ACT_WAIT;`,
  text: "A Mettaur that has just appeared does not act at once. The first time its decision loop runs it arms a pause and hands itself to a plain wait-this-many-frames state. The number stored is 0x1e, which is 30, but the pause covers 31 frames, about half a second, because the counter is tested after it has been reduced, so the frame holding zero is still a waiting frame. It happens once per Mettaur: a marker byte is left set, and that branch is never taken again.",
  highlights: [
    { code: "const METTAUR_SPAWN_WAIT: u16 = 0x1e;",
      text: "The number stored is 0x1e, which is 30" },
    { code: "if self.wait > 0 {",
      text: "the counter is tested after it has been reduced" },
    { code: "self.cur_action = METTAUR_ACT_WAIT;",
      text: "hands itself to a plain wait-this-many-frames state" },
    { code: "self.param4 = METTAUR_SPAWN_WAIT as u8;",
      text: "a marker byte is left set" },
  ],
},

{
  title: "Rebinding an animation",
  codePath: "src/spr.rs",
  code: `pub fn rebind_if_changed(&mut self, cur_anim: usize, cur_anim_copy: &mut usize) -> bool {
    if *cur_anim_copy == cur_anim {
        return false;
    }
    self.bind(cur_anim);
    self.load_frame();
    *cur_anim_copy = cur_anim;
    true
}

// The ordinary per-frame call: pick up any change, then tick.
pub fn update_sprite(&mut self, cur_anim: usize, cur_anim_copy: &mut usize) {
    self.rebind_if_changed(cur_anim, cur_anim_copy);
    self.update();
}`,
  text: "Game logic never plays an animation directly. It writes down which animation this object ought to be showing, and once a frame the sprite side compares that number with its own copy. The same, and nothing happens: the current animation keeps running. Different, and it binds -- points the player at the new list of commands, loads its first picture, and stores the new number as the copy. There are four wrappers around this, differing only in what they skip; one deliberately does not tick on the frame it rebinds.",
  highlights: [
    { code: "if *cur_anim_copy == cur_anim {",
      text: "compares that number with its own copy" },
    { code: "return false;",
      text: "The same, and nothing happens" },
    { code: "self.bind(cur_anim);",
      text: "points the player at the new list of commands" },
    { code: "self.load_frame();",
      text: "loads its first picture" },
    { code: "*cur_anim_copy = cur_anim;",
      text: "stores the new number as the copy" },
  ],
},

{
  title: "Fetch, look up, run",
  codePath: "src/script.rs",
  code: `pub const MAP_SCRIPT_JUMPTABLE: [MapCmd; 71] = [
    MapCmd::End,
    MapCmd::Jump,
    // ... 69 more slots, in the original game's own order
];
fn walk(&mut self, world: &mut MapWorld<'_>) -> Step {
    loop {
        let opcode = match self.code.byte(self.cursor) {
            Some(o) => o,
            None => return self.trap(Trap::PointerOutsideImage(self.cursor)),
        };
        let cmd = match MapCmd::at(opcode) {
            Some(c) => c,
            None => {
                return self.trap(Trap::Unimplemented("MapScriptCommandJumptable", opcode));
            }
        };
        let step = self.dispatch(cmd, opcode, world);`,
  text: "Two parts of the original game are little machines that run a numbered list of commands: the one driving the walk up to a battle, and the one printing every line of text. Both work the same way. Read the byte the cursor points at, use it as a position in a table of 71 entries, run whatever sits there, and if that answer says keep going, read the next byte. The table is copied slot for slot, so command number three here is command number three there.",
  highlights: [
    { code: "pub const MAP_SCRIPT_JUMPTABLE: [MapCmd; 71] = [",
      text: "a table of 71 entries" },
    { code: "let opcode = match self.code.byte(self.cursor) {",
      text: "Read the byte the cursor points at" },
    { code: "let cmd = match MapCmd::at(opcode) {",
      text: "use it as a position" },
    { code: "let step = self.dispatch(cmd, opcode, world);",
      text: "run whatever sits there" },
    { code: "loop {",
      text: "read the next byte" },
  ],
},

{
  title: "A trap instead of a guess",
  codePath: "src/script.rs",
  code: `pub enum Trap {
    NullTableEntry(&'static str, u8),
    Unimplemented(&'static str, u8),
    PointerOutsideImage(u32),
    NativeFunction(u32),
    NoDrawTarget,
}
// Each trap carries the original game's own name for the routine, so a
// stop says exactly which one is missing.
pub fn kind(&self) -> &'static str {
    match self {
        Trap::NullTableEntry(..) => "null table entry",
        Trap::Unimplemented(..) => "unimplemented opcode",
        Trap::PointerOutsideImage(_) => "pointer outside image",
        Trap::NativeFunction(_) => "native function call",
        Trap::NoDrawTarget => "no draw target",
    }
}`,
  text: "Most commands those machines can run are not written yet. Rather than guess what a missing one does, an unwritten slot stops the run and leaves a note: which command it was, under the original game's own name for that routine, and where the cursor stood. Five kinds of note exist, among them a slot the original itself leaves empty and an address that points outside the piece of script the machine holds. A stop that names itself is a list of work; a guess would be a silent wrong answer.",
  highlights: [
    { code: "Trap::Unimplemented(..) => \"unimplemented opcode\",",
      text: "an unwritten slot stops the run and leaves a note" },
    { code: "Trap::NullTableEntry(..) => \"null table entry\",",
      text: "a slot the original itself leaves empty" },
    { code: "Trap::PointerOutsideImage(_) => \"pointer outside image\",",
      text: "an address that points outside the piece of script the machine holds" },
    { code: "pub fn kind(&self) -> &'static str {",
      text: "Five kinds of note exist" },
  ],
},

{
  title: "The scene's switches",
  codePath: "src/fixture.rs",
  code: `// Eight switches packed into one byte: 1 << 0 is the lowest bit
// (value 1), 1 << 7 the highest (value 128).
pub const FLAG_OPEN_WINDOW: u8 = 1 << 0;
pub const FLAG_BLANK_HUD: u8 = 1 << 1;
pub const FLAG_BLANK_BACKDROP: u8 = 1 << 2;
pub const FLAG_AUTO_FIRE: u8 = 1 << 3;
pub const FLAG_SKIP_INTRO: u8 = 1 << 4;
pub const FLAG_RESOLVE_OVER: u8 = 1 << 5;
pub const FLAG_HUD_LIVE: u8 = 1 << 6;
pub const FLAG_TRACE: u8 = 1 << 7;`,
  text: "One byte of the scene description is eight separate switches. Blank the display draws the fight with no boxes, gauge or numbers over it. Blank the background leaves the moving pattern out, so only the field shows. Skip the intro starts with everyone already standing rather than playing the arrival. Resolve makes the fight end properly when the last enemy dies instead of running on. Display live tells a scene that has no enemy at all that its display should still be switched on. Auto fire holds the buster down.",
  highlights: [
    { code: "pub const FLAG_BLANK_HUD: u8 = 1 << 1;",
      text: "Blank the display draws the fight with no boxes, gauge or numbers over it" },
    { code: "pub const FLAG_BLANK_BACKDROP: u8 = 1 << 2;",
      text: "Blank the background leaves the moving pattern out" },
    { code: "pub const FLAG_SKIP_INTRO: u8 = 1 << 4;",
      text: "Skip the intro starts with everyone already standing" },
    { code: "pub const FLAG_RESOLVE_OVER: u8 = 1 << 5;",
      text: "Resolve makes the fight end properly when the last enemy dies" },
    { code: "pub const FLAG_HUD_LIVE: u8 = 1 << 6;",
      text: "Display live tells a scene that has no enemy at all" },
  ],
},

{
  title: "The word the game leaves at boot",
  codePath: "src/main.rs",
  code: `// 0x42415454 is 1111577684, and its four bytes are the letters B A T T.
const BATTLE_MAGIC: u32 = 0x4241_5454;

fn write_battle_marker(magic: u32, frame: u32) {
    unsafe {
        let p = core::ptr::addr_of_mut!(BATTLE_MARKER) as *mut u32;
        core::ptr::write_volatile(p, magic);
        core::ptr::write_volatile(p.add(1), frame);
    }
}

// ... once per frame, from the main loop:
if clocks_visible {
    write_battle_marker(BATTLE_MAGIC, battle_frame);
    battle_frame += 1;
}`,
  text: "Nothing inside the game ever reads this. Eight bytes sit at a fixed spot that the layout file pins to the very start of the machine's spare memory, and every frame the game writes two numbers there: a mark whose four bytes spell BATT, and a count of battle frames so far. Anything watching from outside can find the first frame of the fight by that mark and number every frame after it, instead of counting from the moment the machine was switched on.",
  highlights: [
    { code: "const BATTLE_MAGIC: u32 = 0x4241_5454;",
      text: "a mark whose four bytes spell BATT" },
    { code: "core::ptr::addr_of_mut!(BATTLE_MARKER) as *mut u32",
      text: "Eight bytes sit at a fixed spot" },
    { code: "core::ptr::write_volatile(p.add(1), frame);",
      text: "a count of battle frames so far" },
    { code: "battle_frame += 1;",
      text: "number every frame after it" },
  ],
},

{
  title: "The state block the test reads",
  codePath: "src/main.rs and src/battle.rs",
  code: `// src/main.rs -- forty bytes next to that mark, rewritten every frame.
fn write_oracle_block(bytes: &[u8; 40]) {
    unsafe {
        let p = core::ptr::addr_of_mut!(BATTLE_MARKER)
            .cast::<u8>()
            .add(ORACLE_OFFSET);
        for (i, b) in bytes.iter().enumerate() {
            core::ptr::write_volatile(p.add(i), *b);
        }
    }
}

// src/battle.rs -- what goes into them, in the original game's own units.
b[8..12].copy_from_slice(&self.primary_rng.state().to_le_bytes());
let mm = self.megaman.oracle_fields(true, false);
b[14] = mm.anim;
b[15] = mm.panel_x;
b[20..22].copy_from_slice(&mm.hp.to_le_bytes());`,
  text: "Pixels alone cannot say why two runs of the same fight drift apart. So the game publishes its own state as well: forty bytes just past the boot mark, rewritten every frame, holding the current random number, which animation MegaMan is playing, which panel he stands on and his health. Each is stored the way the original game stores it, not the way our code happens to. Read the same values out of the original and the two lists line up, so the first difference names the thing that moved.",
  highlights: [
    { code: "fn write_oracle_block(bytes: &[u8; 40]) {",
      text: "forty bytes just past the boot mark" },
    { code: "b[8..12].copy_from_slice(&self.primary_rng.state().to_le_bytes());",
      text: "the current random number" },
    { code: "b[14] = mm.anim;",
      text: "which animation MegaMan is playing" },
    { code: "b[15] = mm.panel_x;",
      text: "which panel he stands on" },
    { code: "b[20..22].copy_from_slice(&mm.hp.to_le_bytes());",
      text: "and his health" },
  ],
},

{
  title: "The random number generator",
  codePath: "src/ai.rs",
  code: `// The seed a battle starts from unless the scene supplies one:
// 0xa338244f, which is 2738365519.
pub const DEFAULT_SEED: u32 = 0xa338_244f;

pub fn next(&mut self) -> u32 {
    // Rotate left one bit, add one, then flip the bits picked out by
    // 0x873ca9e5, which is 2268899813 -- the original game's own constant.
    self.0 = self.0.rotate_left(1).wrapping_add(1) ^ 0x873c_a9e5;
    self.0
}

// The same step with the top bit cleared, so the answer is never negative.
pub fn positive(&mut self) -> u32 {
    self.next() & 0x7fff_ffff
}`,
  text: "Every enemy that rolls for a decision draws from one shared number, changed by the same rule the original game uses. A call rotates the current value left by one bit, adds one, and flips the bits picked out by a fixed constant. A second call clears the top bit so the answer is never negative, which is the form the enemy code asks for. Rule and starting value both match, so an enemy that rolls in the original rolls the same way here, on the same frame.",
  highlights: [
    { code: "self.0 = self.0.rotate_left(1).wrapping_add(1) ^ 0x873c_a9e5;",
      text: "rotates the current value left by one bit, adds one, and flips the bits picked out by a fixed constant" },
    { code: "self.next() & 0x7fff_ffff",
      text: "clears the top bit so the answer is never negative" },
    { code: "pub const DEFAULT_SEED: u32 = 0xa338_244f;",
      text: "Rule and starting value both match" },
    { code: "pub fn positive(&mut self) -> u32 {",
      text: "the form the enemy code asks for" },
  ],
},

{
  title: "Who owns which panel",
  codePath: "src/field.rs",
  code: `// Eighteen panels, one flag each: the three left columns start as the
// player's, the three right ones as the enemy's.
enemy_owned: core::array::from_fn(|i| i % COLS as usize >= 3),

// AreaGrab takes the enemy's front panel on each of the three rows.
pub fn steal_column(&mut self, occupied: u32) -> Vec<(i32, i32)> {
    let mut taken = Vec::new();
    for row in 1..=ROWS {
        let (lo, _) = self.half(true, row);
        if lo <= COLS
            && self.enemy_owned(lo, row)
            && lo > 1
            && occupied & panel_bit(lo, row) == 0
        {
            self.enemy_owned[index(lo, row)] = false;
            self.dirty |= panel_bit(lo, row);
            taken.push((lo, row));`,
  text: "Ownership is not a line down the middle of the screen. It is one flag per panel, eighteen of them, set at the start so the three columns on the left belong to the player and the three on the right to the enemy. AreaGrab walks the three rows and flips the enemy's frontmost panel on each, but only where nobody is standing on it, and only if the enemy would still be left with a panel. Each flip marks that panel so the drawing code repaints it alone.",
  highlights: [
    { code: "enemy_owned: core::array::from_fn(|i| i % COLS as usize >= 3),",
      text: "one flag per panel, eighteen of them" },
    { code: "self.enemy_owned[index(lo, row)] = false;",
      text: "flips the enemy's frontmost panel on each" },
    { code: "occupied & panel_bit(lo, row) == 0",
      text: "only where nobody is standing on it" },
    { code: "&& lo > 1",
      text: "only if the enemy would still be left with a panel" },
    { code: "self.dirty |= panel_bit(lo, row);",
      text: "marks that panel so the drawing code repaints it alone" },
  ],
},

{
  title: "The chimes before the window",
  codePath: "src/battle.rs",
  code: `// 60 frames is one second at sixty frames a second.
const GAUGE_PAUSE: u16 = 60;

if self.gauge == GAUGE_FULL && self.open_window_allowed() {
    self.gauge_pause = GAUGE_PAUSE;
}

// ... elsewhere in the same update, that countdown holds the fight:
} else if self.gauge_pause > 0 && self.open_window_allowed() {
    self.gauge_pause -= 1;
    if self.gauge_pause == 0 {
        self.deck.compact();`,
  text: "A full gauge does not open the window by itself. Reaching the top sets a countdown of 60 frames, one second, and for those frames the fight is held still while the chimes play. When the countdown reaches zero the deck is packed up so the chips still unused sit at the front, the first five of them are offered, and only then does the window begin to slide in. That order matters: the five you are shown are chosen at the end of the pause, not when the gauge filled.",
  highlights: [
    { code: "const GAUGE_PAUSE: u16 = 60;",
      text: "a countdown of 60 frames, one second" },
    { code: "self.gauge_pause = GAUGE_PAUSE;",
      text: "Reaching the top sets" },
    { code: "self.gauge_pause -= 1;",
      text: "for those frames the fight is held still" },
    { code: "if self.gauge_pause == 0 {",
      text: "When the countdown reaches zero" },
    { code: "self.deck.compact();",
      text: "the deck is packed up so the chips still unused sit at the front" },
  ],
},

{
  title: "Which chips can go together",
  codePath: "src/custom.rs",
  code: `fn allowed(&self, slot: usize) -> bool {
    let Some(offer) = self.slots[slot] else {
        return false;
    };
    // Five is the whole hand; nothing more fits.
    if self.picks.len() >= HAND_SIZE {
        return false;
    }
    if self.picks.is_empty() {
        return true;
    }
    // ... gather the chips already picked, then:
    let name = picked[FIRST_PICK].chip.name();
    if picked.iter().all(|o| o.chip.name() == name) && offer.chip.name() == name {
        return true;
    }`,
  text: "The window offers five chips and you may take five, but not any five. The first pick is free. After that one may join only if it agrees with what is there already: either every chip picked so far carries the same name and this one carries it too, or their letter codes agree, with the star code agreeing with anything. Chips that cannot join are drawn dimmed, and the question is asked again after every pick, so the dimming follows the hand as it grows.",
  highlights: [
    { code: "if self.picks.len() >= HAND_SIZE {",
      text: "you may take five, but not any five" },
    { code: "if self.picks.is_empty() {",
      text: "The first pick is free" },
    { code: "let name = picked[FIRST_PICK].chip.name();",
      text: "every chip picked so far carries the same name" },
    { code: "offer.chip.name() == name",
      text: "and this one carries it too" },
  ],
},

{
  title: "The window leaves and the field follows",
  codePath: "src/custom.rs and src/battle.rs",
  code: `// src/custom.rs -- ten steps of 12 pixels back out to 120, then gone.
Phase::Closing { x } if x < SLIDE_FROM => {
    let x = (x + SLIDE_STEP).min(SLIDE_FROM);
    // ... repaint the columns the window has vacated, then:
    if x == SLIDE_FROM {
        Phase::Done
    } else {
        Phase::Closing { x }
    }
}

// src/battle.rs -- the field walks back over the same ten steps.
self.field_slide = if self.field_slide < want {
    (self.field_slide + FIELD_SLIDE_STEP).min(want)
} else {
    self.field_slide.saturating_sub(FIELD_SLIDE_STEP).max(want)
};
let camera_half_px = -(self.field_slide as i32);`,
  text: "Closing is the opening run backwards: ten steps of 12 pixels carry the window from the left edge back to 120 pixels off screen, and the tenth step both arrives and finishes, so no frame is spent parked out there. The field does not sit still meanwhile. The original game pans its camera from inside the window's own slide, one and a half pixels a step, 15 pixels over the ten, so this side counts in half pixels -- 3 a step, 30 in all -- and divides down only when it uses the number.",
  highlights: [
    { code: "let x = (x + SLIDE_STEP).min(SLIDE_FROM);",
      text: "ten steps of 12 pixels carry the window" },
    { code: "if x == SLIDE_FROM {",
      text: "the tenth step both arrives and finishes" },
    { code: "(self.field_slide + FIELD_SLIDE_STEP).min(want)",
      text: "one and a half pixels a step, 15 pixels over the ten" },
    { code: "let camera_half_px = -(self.field_slide as i32);",
      text: "counts in half pixels -- 3 a step, 30 in all" },
  ],
},

{
  title: "Charging the buster",
  codePath: "src/battle.rs",
  code: `// 101 frames is about one and two thirds seconds of holding B.
const CHARGE_FRAMES: u16 = 101;

if input.is_pressed(Button::B) {
    self.charge = self.charge.saturating_add(1);
} else {
    if self.charge >= CHARGE_FRAMES {
        self.megaman.attack_charged();
    } else if self.charge > 0 && !self.megaman.is_busy() {
        let spec = self.megaman.buster_spec();
        self.megaman.attack(spec);
        self.buster_arm_in = BUSTER_ARM_DELAY;
    }
    self.charge = 0;
}`,
  text: "Holding B just counts frames. Letting go decides which shot happens. Past 101 frames, about one and two thirds seconds, it is the charged shot, worth 20 damage, and that one really travels: a hitbox hopping panel to panel. Below that it is the plain buster, worth 2, and the plain buster never crosses the field at all -- whoever stands on the row is simply checked on the spot. Either way the count returns to zero, and the raised-arm pose waits a few frames so the navi stands up first.",
  highlights: [
    { code: "const CHARGE_FRAMES: u16 = 101;",
      text: "Past 101 frames, about one and two thirds seconds" },
    { code: "self.charge = self.charge.saturating_add(1);",
      text: "Holding B just counts frames" },
    { code: "self.megaman.attack_charged();",
      text: "it is the charged shot, worth 20 damage" },
    { code: "self.charge = 0;",
      text: "the count returns to zero" },
    { code: "self.buster_arm_in = BUSTER_ARM_DELAY;",
      text: "the raised-arm pose waits a few frames" },
  ],
},

{
  title: "The shockwave hits a frame after it arrives",
  codePath: "src/shot.rs",
  code: `// Report last frame's arrival, then clear the latch.
if self.lights_panel {
    self.hopped = self.hop_pending;
    self.hop_pending = false;
} else {
    self.hopped = false;
}

// ... and further down, on the frame the hitbox actually moves:
if self.lights_panel {
    self.hop_pending = true;
} else {
    self.hopped = true;
}`,
  text: "Most shots hurt whoever is on the panel the moment they land on it. A shockwave does not. In the original game the newly spawned segment offers its hitbox during its own setup, which runs after the check against the player has already happened that frame, so the damage lands on the next one. Here that is a one-frame latch: arriving sets a pending flag, and the following frame turns that flag into the arrival everyone else reads. Same picture, hit one frame later.",
  highlights: [
    { code: "self.hopped = self.hop_pending;",
      text: "the following frame turns that flag into the arrival everyone else reads" },
    { code: "self.hop_pending = true;",
      text: "arriving sets a pending flag" },
    { code: "self.hopped = true;",
      text: "Most shots hurt whoever is on the panel the moment they land on it" },
    { code: "self.hop_pending = false;",
      text: "a one-frame latch" },
  ],
},

{
  title: "The face slides out of the way",
  codePath: "src/emotion.rs",
  code: `const LEFT: (i32, i32) = (0, 18);
const RIGHT: (i32, i32) = (32, 18);

// Every object of the display is pushed right by the chip window's own
// slide counter: 0 with no window, 120 pixels with it fully open.
pub fn show(&self, frame: &mut GraphicsFrame, x_offset: i32) {
    for (sprite, at) in [(&self.wide, LEFT), (&self.narrow, RIGHT)] {
        Object::new(sprite.clone())
            .set_priority(Priority::P2)
            .set_pos((at.0 + x_offset, at.1))
            .show(frame);
    }
}`,
  text: "The face in the blue frame at the top left is two sprites side by side, a wide one and a narrow one, drawn over the background rather than built into it -- which is why it survives when the field is stripped away. They are not nailed to the screen either. The original game adds the chip window's own slide counter to their position, so while the window covers the left of the screen the whole display rides 120 pixels right and walks back as the window leaves.",
  highlights: [
    { code: "const LEFT: (i32, i32) = (0, 18);",
      text: "two sprites side by side, a wide one and a narrow one" },
    { code: ".set_priority(Priority::P2)",
      text: "drawn over the background rather than built into it" },
    { code: ".set_pos((at.0 + x_offset, at.1))",
      text: "adds the chip window's own slide counter to their position" },
    { code: "pub fn show(&self, frame: &mut GraphicsFrame, x_offset: i32) {",
      text: "rides 120 pixels right" },
  ],
},

{
  title: "From the last hit to the results",
  codePath: "src/battle.rs",
  code: `if over && self.shown.is_none() && self.fade_out == 0 {
    // The banner the fight ends on, put up once.
    if !self.banner_done && self.results_delay <= RESULTS_DELAY {
        self.banner_done = true;
        let message = if self.megaman.is_defeated() {
            banner::MEGAMAN_DELETED
        } else {
            banner::ENEMY_DELETED
        };
        self.banner = Some(Banner::new(self.banner_assets, message));
    }
    if self.results_delay > 0 {
        self.results_delay -= 1;
    } else {
        let won = !self.megaman.is_defeated();`,
  text: "A killing blow does not end the battle on the spot. One event fires, the end sequence, and everything hangs off it: the display is torn down, a wide ribbon of letters unrolls across the middle of the screen, and a counter of 110 frames -- close to two seconds -- starts. The ribbon goes up exactly once, held back by a flag, because this same code runs every frame afterwards. When the counter empties the results window slides in. If MegaMan was the one deleted, the same path shows his message instead.",
  highlights: [
    { code: "if over && self.shown.is_none() && self.fade_out == 0 {",
      text: "One event fires, the end sequence, and everything hangs off it" },
    { code: "self.banner_done = true;",
      text: "goes up exactly once, held back by a flag" },
    { code: "banner::ENEMY_DELETED",
      text: "a wide ribbon of letters unrolls across the middle of the screen" },
    { code: "self.results_delay -= 1;",
      text: "a counter of 110 frames -- close to two seconds -- starts" },
    { code: "banner::MEGAMAN_DELETED",
      text: "If MegaMan was the one deleted" },
  ],
},

{
  title: "The results screen's phases",
  codePath: "src/results.rs",
  code: `self.phase = match self.phase {
    Phase::Sliding { x, hold } if hold > 0 => Phase::Sliding { x, hold: hold - 1 },
    Phase::Sliding { x, .. } if x < REST_X => {
        let x = (x + SLIDE_STEP).min(REST_X);
        self.blit_needed = true;
        Phase::Sliding { x, hold: 0 }
    }
    Phase::Sliding { .. } => Phase::Waiting,
    Phase::Waiting if confirm => Phase::Dismissing {
        ticks: DISMISS_FRAMES,
    },
    Phase::Waiting => Phase::Waiting,
    Phase::Revealing { left } if left > 1 => Phase::Revealing { left: left - 1 },
    Phase::Revealing { .. } => Phase::Cooldown {
        ticks: COOLDOWN_FRAMES,
    },
    Phase::Cooldown { ticks } if ticks > 1 => Phase::Cooldown { ticks: ticks - 1 },
    Phase::Cooldown { .. } => Phase::RewardWait,`,
  text: "The window walks a short list of named states, one arm each. It holds a moment, slides in 16 pixels a frame, then waits with a blinking prompt. Your press does not close it if you won: it goes to a reveal where the reward is drawn, then a cooldown of 30 frames, half a second, in which presses are ignored on purpose, and only then does it wait for the press that really dismisses it. A loss has no reward and leaves straight away.",
  highlights: [
    { code: "Phase::Sliding { x, hold } if hold > 0 => Phase::Sliding { x, hold: hold - 1 },",
      text: "It holds a moment" },
    { code: "let x = (x + SLIDE_STEP).min(REST_X);",
      text: "slides in 16 pixels a frame" },
    { code: "Phase::Sliding { .. } => Phase::Waiting,",
      text: "then waits with a blinking prompt" },
    { code: "Phase::Revealing { left } if left > 1 => Phase::Revealing { left: left - 1 },",
      text: "it goes to a reveal where the reward is drawn" },
    { code: "Phase::Cooldown { ticks } if ticks > 1 => Phase::Cooldown { ticks: ticks - 1 },",
      text: "a cooldown of 30 frames, half a second, in which presses are ignored on purpose" },
  ],
},

{
  title: "One copy instead of hundreds",
  codePath: "vendor/agb/agb/src/display/tiled/regular_background.rs and src/results.rs",
  code: `pub fn copy_map_block(
    &mut self,
    pos: impl Into<Vector2D<i32>>,
    width: usize,
    words: &[u16],
) -> &mut Self {
    // ... nested loops rather than one flat index: a flat index needs two
    // software divisions per cell, which cost more than the whole copy.
    for dy in 0..rows {
        for (dx, &word) in words[dy * width..(dy + 1) * width].iter().enumerate() {
            let at = size.gba_offset(Vector2D::new(origin.x + dx as i32, origin.y + dy as i32));
            let old = self.tiles.get(at);
            let new = Tile(word);
            if old == new {
                continue;

// src/results.rs -- the whole window handed over in one call.
shown.bg.copy_map_block(MAP_ORIGIN, MAP_W, &block);`,
  text: "The results window is a grid of 24 by 18 cells that slides across the screen, so every frame it moves, all of it has to be written again. Doing that a cell at a time meant a separate lookup for each, and 432 of those do not fit between two screen refreshes. This is the fix, and it lives in the graphics library the project keeps its own copy of: hand over the block and it writes the cells straight in, skipping any whose value has not changed.",
  highlights: [
    { code: "pub fn copy_map_block(",
      text: "hand over the block and it writes the cells straight in" },
    { code: "let old = self.tiles.get(at);",
      text: "a separate lookup for each" },
    { code: "if old == new {",
      text: "skipping any whose value has not changed" },
    { code: "shown.bg.copy_map_block(MAP_ORIGIN, MAP_W, &block);",
      text: "all of it has to be written again" },
  ],
},

{
  title: "Seeding the background for a scene",
  codePath: "src/battle.rs",
  code: `// A scene compared against a snapshot of the real game starts where the
// snapshot is. 0xFFFF, which is 65535, means "no seed given".
match self.fixture {
    Some(f) if f.art_entry != FIXTURE_UNSET => {
        backdrop.seed(
            f.art_entry as usize,
            f.art_timer,
            f.scroll_xq as u32,
            f.scroll_yq as u32,
        );
    }
    Some(_) => {}
    None => {}
}
backdrop.prime(gfx);`,
  text: "The pattern behind a fight runs on two clocks that start when the battle starts, so a fight already thousands of frames old is somewhere in the middle of both. A scene description can therefore carry four numbers: which artwork step is showing, how many frames are left on it, and how far the pattern has slid across and down. Given them, the background begins there rather than at the beginning. A scene that leaves the first at 65535, all ones, gets the ordinary fresh start.",
  highlights: [
    { code: "Some(f) if f.art_entry != FIXTURE_UNSET => {",
      text: "leaves the first at 65535, all ones" },
    { code: "f.art_entry as usize,",
      text: "which artwork step is showing" },
    { code: "f.art_timer,",
      text: "how many frames are left on it" },
    { code: "f.scroll_xq as u32,",
      text: "how far the pattern has slid across and down" },
    { code: "backdrop.prime(gfx);",
      text: "the background begins there rather than at the beginning" },
  ],
},

];
