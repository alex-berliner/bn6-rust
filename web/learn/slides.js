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
//             A number is explained by what it counts or selects, never by
//             converting hex to decimal for its own sake; give the decimal
//             only when the size is the point (0x100 is 256, life size).
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
  code: `// The four bytes of 0x42415454 are the letters B A T T.
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
// 0xa338244f.
pub const DEFAULT_SEED: u32 = 0xa338_244f;

pub fn next(&mut self) -> u32 {
    // Rotate left one bit, add one, then flip the bits picked out by
    // 0x873ca9e5 -- the original game's own constant.
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
// snapshot is. 0xFFFF, means "no seed given".
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

{
  title: "The folder is dealt from the top",
  codePath: "src/deck.rs",
  code: "    pub fn new(folder: [u16; FOLDER_SIZE], rng: &mut Rng) -> Self {\n        let mut chips = folder;\n        let len = chips.len() as u32;\n        for _ in 0..len {\n            let i = (rng.positive() % len) as usize;\n            let j = (rng.positive() % len) as usize;\n            chips.swap(i, j);\n        }\n        Self { chips }\n    }\n\n    // ...\n\n    pub fn offer(&self, count: usize) -> &[u16] {\n        let live = self.chips.iter().take_while(|&&c| c != EMPTY).count();\n        &self.chips[..live.min(count)]\n    }\n\n    /// Remove an offered chip by its slot index.\n    pub fn take(&mut self, slot: usize) -> u16 {\n        core::mem::replace(&mut self.chips[slot], EMPTY)\n    }",
  text: "Before a fight, the player's folder, the thirty battle chips they carry, is shuffled once. The shuffle makes thirty swaps, one per chip, each trading two places picked by the random number generator. Nothing points at a next card: the chip window simply offers the first live entries in the list. A chip the player takes is overwritten with EMPTY, a marker meaning this slot is used up. Left out here is the step that slides the survivors back to the front each time the window opens, so chips passed over come round again and the folder only shrinks.",
  highlights: [
    { code: "for _ in 0..len {",
      text: "makes thirty swaps" },
    { code: "chips.swap(i, j);",
      text: "trading two places" },
    { code: "take_while(|&&c| c != EMPTY)",
      text: "offers the first live entries" },
    { code: "core::mem::replace(&mut self.chips[slot], EMPTY)",
      text: "overwritten with EMPTY" },
    { code: "// ...",
      text: "Left out here" },
  ],
},

{
  title: "The ribbon that unrolls",
  codePath: "src/banner.rs",
  code: "pub const SCALE: [u16; 58] = [\n    768, 640, 512, 384, 256, 208, 224, // unrolling, with an overshoot\n    // ...\n    224, 208, 256, 384, 512, 640, 768, 896, // rolling back up\n];\n\n// ...\n    pub fn update(&mut self) -> bool {\n        self.t += 1;\n        self.t < SCALE.len()\n    }\n\n    pub fn show(&self, frame: &mut GraphicsFrame) {\n        let Some(&scale) = SCALE.get(self.t) else {\n            return;\n        };\n        let matrix = AffineMatrixObject::new(AffineMatrix::<Num<i32, 8>> {\n            a: Num::from_raw(0x100),\n            // ...\n            d: Num::from_raw(scale as i32),\n            // ...",
  text: "Messages such as BATTLE START! cross the screen on a ribbon of five sprites, small pictures the hardware can place anywhere. It can also squash one, and SCALE lists how much for each of the 58 frames (about one second) the ribbon is up. The width stays at 0x100, which is 256 and means life size; the height gets the frame's entry, and bigger is flatter, so 768 draws a third of the height. The counter t picks the entry. Left out: rows held at life size, the letter-building code, the matrix entries left at zero and the loop placing the pieces.",
  highlights: [
    { code: "768, 640, 512, 384, 256, 208, 224,",
      text: "bigger is flatter" },
    { code: "self.t += 1;",
      text: "The counter t picks the entry" },
    { code: "a: Num::from_raw(0x100),",
      text: "The width stays at 0x100" },
    { code: "d: Num::from_raw(scale as i32),",
      text: "the height gets the frame's entry" },
    { code: "[u16; 58]",
      text: "58 frames (about one second)" },
  ],
},

{
  title: "How the Gunner finds its target",
  codePath: "src/gunner.rs",
  code: "        if let Some(dwell) = self.lock {\n            if dwell > 1 {\n                self.lock = Some(dwell - 1);\n                return CursorState::Travelling;\n            }\n            return CursorState::Locked((self.col(), self.row));\n        }\n        self.x += CURSOR_SPEED * self.dx;\n        self.beat -= 1;\n        if self.beat == 0 {\n            self.beat = CURSOR_BEAT;\n            let col = self.col();\n            if !(1..=field::COLS).contains(&col) {\n                return CursorState::Lost;\n            }\n            if (col, self.row) == target {\n                self.lock = Some(LOCK_FRAMES);\n                self.player.play(1);\n            }\n        }\n        CursorState::Travelling",
  text: "The Gunner is a virus that never moves. When the player steps into its row, it sends out a cursor that slides along that row, 3 pixels a frame. Every 13 frames, roughly the time it takes to cross one panel (one square of the field), the cursor checks the panel it is over. If the player stands there, the cursor holds still for 24 frames (under half a second) and then reports that panel as Locked, the cue to fire three shots at it. If the cursor runs off the end of the field, it reports Lost and the Gunner goes back to waiting.",
  highlights: [
    { code: "self.x += CURSOR_SPEED * self.dx;",
      text: "3 pixels a frame" },
    { code: "self.beat = CURSOR_BEAT;",
      text: "Every 13 frames" },
    { code: "self.lock = Some(LOCK_FRAMES);",
      text: "holds still for 24 frames" },
    { code: "return CursorState::Locked((self.col(), self.row));",
      text: "reports that panel as Locked" },
    { code: "return CursorState::Lost;",
      text: "it reports Lost" },
  ],
},

{
  title: "A thrown bomb climbs, slows and falls",
  codePath: "src/battle.rs",
  code: "const BOMB_VX: i32 = 0x2e666;\nconst BOMB_VZ: i32 = 0x20666;\nconst BOMB_GRAVITY: i32 = 0x2800;\n// ...\nimpl Bomb {\n    fn step(&mut self) {\n        self.x += self.vx;\n        if self.moves_before_falling {\n            self.z += self.vz;\n            self.vz -= self.gravity;\n        } else {\n            self.vz -= self.gravity;\n            self.z += self.vz;\n        }\n    }\n\n    /// Screen position of the bomb; the game truncates Y and Z separately.\n    fn position(&self) -> (i32, i32) {\n        (self.x >> Q16_SHIFT, (self.y >> Q16_SHIFT) - (self.z >> Q16_SHIFT))\n    }",
  text: "A thrown bomb keeps its position in tiny units, 65536 to a pixel, so it can move by fractions of a pixel. Every frame, step pushes it forward by 0x2e666 of those units, about 2.9 pixels. Its climbing speed starts at 0x20666, about 2 pixels a frame, and gravity takes 0x2800, a sixth of a pixel, off it every frame, so the bomb rises, slows and drops. The lines left out hold the bomb's other settings. To draw it, position drops the fractions and lifts the bomb above its shadow by its height.",
  highlights: [
    { code: "self.x += self.vx;",
      text: "pushes it forward by 0x2e666" },
    { code: "const BOMB_VZ: i32 = 0x20666;",
      text: "starts at 0x20666" },
    { code: "const BOMB_GRAVITY: i32 = 0x2800;",
      text: "gravity takes 0x2800" },
    { code: "(self.y >> Q16_SHIFT) - (self.z >> Q16_SHIFT)",
      text: "lifts the bomb above its shadow by its height" },
  ],
},

{
  title: "Pressing A plays the next chip",
  codePath: "src/battle.rs",
  code: "if !paused {\n    // A uses the next chip of the hand when the navi is free\n    // ...\n    if input.is_just_pressed(Button::A) && self.chip_use_in == 0 {\n        self.chip_use_in = CHIP_USE_DELAY;\n    }\n    if self.chip_use_in > 0 {\n        self.chip_use_in -= 1;\n        if self.chip_use_in == 0 && !self.megaman.is_busy() && self.hand_at < self.hand.len()\n        {\n            let chip = self.hand[self.hand_at];\n            self.hand_at += 1;\n            self.use_chip(chip);\n        }\n    }",
  text: "The hand is the short list of chips picked for this turn, played front to back. Pressing A does not fire a chip at once: it starts a small countdown, CHIP_USE_DELAY, three frames (a twentieth of a second) long, because the real game waits that long too, as the comment lines left out explain. When it reaches zero, the chip goes off only if MegaMan is free, not mid-move or mid-attack, and the hand is not empty. A marker then moves one place along the hand, and use_chip picks what that chip does: a sword swing, a bomb throw, a barrier.",
  highlights: [
    { code: "input.is_just_pressed(Button::A)",
      text: "Pressing A does not fire a chip at once" },
    { code: "self.chip_use_in = CHIP_USE_DELAY;",
      text: "starts a small countdown" },
    { code: "!self.megaman.is_busy()",
      text: "not mid-move or mid-attack" },
    { code: "self.hand_at += 1;",
      text: "A marker then moves one place along the hand" },
    { code: "self.use_chip(chip);",
      text: "use_chip picks what that chip does" },
  ],
},

{
  title: "A press of the arrows becomes a step",
  codePath: "src/battle.rs",
  code: "for (button, dx, dy) in [\n    (Button::Right, 1, 0),\n    (Button::Left, -1, 0),\n    (Button::Down, 0, 1),\n    (Button::Up, 0, -1),\n] {\n    if input.is_just_pressed(button) && !paused {\n        let blocked = self\n            .enemies\n            .iter()\n            .filter(|e| e.is_present())\n            .fold(self.panels.other_half(false), |m, e| m | e.occupancy());\n        if self.megaman.step(dx, dy, blocked) {\n            self.moves = self.moves.saturating_add(1);\n        }\n    }\n}",
  text: "Each arrow button comes paired with the step it asks for: 1 is one panel right or down, -1 one panel left or up. Only the frame the button goes down counts, so holding it does not repeat. Next comes the list of panels MegaMan may not enter, one yes-or-no bit per panel. It starts with every panel the enemy owns, then adds each living enemy's panel plus any panel it is moving into. The step is refused if MegaMan is busy, or the panel is on that list or off the board; a step that works adds to a move count.",
  highlights: [
    { code: "(Button::Left, -1, 0),",
      text: "-1 one panel left or up" },
    { code: "input.is_just_pressed(button)",
      text: "Only the frame the button goes down counts" },
    { code: "self.panels.other_half(false)",
      text: "every panel the enemy owns" },
    { code: "e.occupancy()",
      text: "each living enemy's panel plus any panel it is moving into" },
    { code: "self.moves = self.moves.saturating_add(1);",
      text: "adds to a move count" },
  ],
},

{
  title: "Dialogue is letters and commands in one stream",
  codePath: "src/script.rs",
  code: "loop {\n    let byte = match self.archive.byte(self.cursor) {\n        Some(b) => b,\n        None => return self.trap(Trap::PointerOutsideImage(self.cursor)),\n    };\n    let step = if byte >= TS_COMMANDS_START {\n        // ... unless the letter countdown holds it back a frame:\n        match TextCmd::at(byte) {\n            Some(cmd) => self.text_dispatch(cmd, byte, &mut draw, input),\n            // ... a command not written yet stops the script by name\n        }\n    } else {\n        self.draw_char(byte, &mut draw)\n    };\n    self.write_back_cursor();\n    if step != Step::Again {\n        return step;\n    }\n}",
  text: "A line of dialogue is stored as a row of bytes, and this loop reads it. Each pass takes the byte under the cursor, which marks how far into the text it has got. A byte below 0xE5, that is below 229, is a letter, and draw_char puts it in the box. A byte of 229 or above is a command, such as wait for a button, and the command table picks which one runs. Each step then says go on or stop until next frame. Left out: a countdown that can delay a command, and a stop for unwritten commands.",
  highlights: [
    { code: "self.archive.byte(self.cursor)",
      text: "the byte under the cursor" },
    { code: "self.draw_char(byte, &mut draw)",
      text: "draw_char puts it in the box" },
    { code: "byte >= TS_COMMANDS_START",
      text: "A byte of 229 or above is a command" },
    { code: "TextCmd::at(byte)",
      text: "the command table picks which one runs" },
    { code: "step != Step::Again",
      text: "stop until next frame" },
  ],
},

{
  title: "MegaMan waits out the chip window",
  codePath: "src/battle.rs",
  code: "let navi_update = objects::t1_player_entry(&mut self.megaman, self.seq.state);\n// ...\n// executor runs FIRST, then the sequencer handler is re-entered on\n// the same frame. With the block here the release edge fires AFTER\n// the player's per-tick work on the SEQ_04 -> SEQ_08 frame.\nmatch self.seq.state {\n    SEQ_20 if self.seq.age >= 1 => self.seq.transition(SEQ_24),\n    SEQ_00 if self.seq.age >= 2 => self.seq.transition(SEQ_04),\n    SEQ_04 if self.seq.age >= SEQ04_FRAMES - 1 => self.seq.transition(SEQ_08),\n    SEQ_20 | SEQ_00 | SEQ_04 => self.seq.age += 1,\n    _ => {}\n}",
  text: "The battle keeps a phase number. Each name, like SEQ_08 for the fight, is the value the real game stores. Four phases cover the chip window: opening, open, a short settle after it closes, and the banner wait. MegaMan's routine gets the phase first and returns at once in those four, so he stays frozen. Then a frame counter moves the phase on: the opening leaves at 1, the settle at 2, the banner wait at 59, which counting from 0 makes 60 frames, one second. The comment's executor is MegaMan's routine and its sequencer is the phase keeper. The cut part names the game's routines.",
  highlights: [
    { code: "objects::t1_player_entry(&mut self.megaman, self.seq.state)",
      text: "MegaMan's routine gets the phase first" },
    { code: "self.seq.age += 1",
      text: "a frame counter" },
    { code: "SEQ_20 if self.seq.age >= 1",
      text: "the opening leaves at 1" },
    { code: "SEQ_00 if self.seq.age >= 2",
      text: "the settle at 2" },
    { code: "SEQ04_FRAMES - 1",
      text: "the banner wait at 59" },
  ],
},

{
  title: "A broken panel comes back",
  codePath: "src/field.rs",
  code: "PANEL_BROKEN => {\n    self.regen[i] = self.regen[i].saturating_sub(1);\n    if self.regen[i] == 0 {\n        self.types[i] = PANEL_NORMAL as u8;\n        self.regen[i] = REGEN_FRAMES;\n        anim = PANEL_NORMAL as u8;\n    } else if self.regen[i] <= BLINK_FRAMES {\n        // Bit 1 of the countdown, so two frames of each.\n        anim = if self.regen[i] & 2 != 0 {\n            PANEL_NORMAL as u8\n        } else {\n            PANEL_BROKEN as u8\n        };\n    }\n}\n// A cracked panel gives way once whoever was standing on it\n// has gone, not when they arrive.\nPANEL_CRACKED => {\n    if self.occupied_last & bit != 0 && occupied & bit == 0 {\n// ...",
  text: "A panel on the field can be whole, cracked or broken. Once a frame the game walks every panel and moves it along. A cracked panel waits until whoever stood on it steps off, then breaks. A broken panel counts regen down from ten seconds' worth of frames, and at zero it turns back into a normal panel. During the final second, BLINK_FRAMES, it swaps between its broken and normal pictures every two frames as a warning. The lines left out finish the cracked branch: start the timer and draw the panel broken.",
  highlights: [
    { code: "saturating_sub(1)",
      text: "counts regen down" },
    { code: "self.regen[i] == 0",
      text: "at zero it turns back into a normal panel" },
    { code: "self.regen[i] <= BLINK_FRAMES",
      text: "During the final second" },
    { code: "self.regen[i] & 2 != 0",
      text: "every two frames" },
    { code: "self.occupied_last & bit != 0 && occupied & bit == 0",
      text: "steps off, then breaks" },
  ],
},

{
  title: "A sprite picture is a stack of pieces",
  codePath: "src/spr.rs",
  code: "pub fn oam(&self, i: usize) -> Oam {\n    let o = self.oam + 4 + i * 6;\n    let flags = self.data[o + 5];\n    Oam {\n        tile: self.u16_at(o),\n        x: self.data[o + 2] as i8,\n        y: self.data[o + 3] as i8,\n        size: size_from_bits(self.data[o + 4]),\n        hflip: flags & 1 != 0,\n        vflip: flags & 2 != 0,\n        pal_offset: flags >> 4,\n    }\n}",
  text: "The GBA draws moving things as hardware objects: small rectangles of pixels the chip paints over the background. One picture of a character is several of them placed together. Each piece is stored as six bytes, after a short header at the start of the list. The first two name the tile art, the next two are signed nudges sideways and up or down from the character's anchor point, the fifth picks the rectangle's shape, and the last holds flags: mirror sideways, mirror upside down, and in its top half a shift to a different set of colours.",
  highlights: [
    { code: "i * 6",
      text: "six bytes" },
    { code: "tile: self.u16_at(o)",
      text: "name the tile art" },
    { code: "size_from_bits(self.data[o + 4])",
      text: "picks the rectangle's shape" },
    { code: "hflip: flags & 1 != 0",
      text: "mirror sideways" },
    { code: "flags >> 4",
      text: "a different set of colours" },
  ],
},

{
  title: "How the swordsman closes in",
  codePath: "src/ai.rs",
  code: "match self.style {\n    Style::Thrust => {\n        // Row first, so the approach reads as lining up.\n        let (col, row) = me.panel();\n        let want = (field::half(true).0, target.1);\n        if row != want.1 {\n            me.step(0, (want.1 - row).signum(), blocked);\n            self.pause = MOVE_PAUSE;\n        } else if col != want.0 {\n            me.step((want.0 - col).signum(), 0, blocked);\n            self.pause = MOVE_PAUSE;\n        } else {\n            me.attack(actor::THRUST);\n            self.pause = ATTACK_PAUSE;\n        }\n    }\n// ...",
  text: "The thrusting swordsman wants to stand in the player's row, on the front column of its own side. Each time it is free it compares where it is with that spot. If its row is wrong it steps one panel up or down; signum turns any distance into a single step. Otherwise, if the column is wrong, it steps sideways. Once both match, it thrusts. Then it rests: MOVE_PAUSE after a step is 29 frames, about half a second, and ATTACK_PAUSE after a thrust is 87 frames, near a second and a half. The other enemy kinds' branches are left out.",
  highlights: [
    { code: "let want = (field::half(true).0, target.1);",
      text: "on the front column of its own side" },
    { code: "if row != want.1 {",
      text: "If its row is wrong" },
    { code: "(want.1 - row).signum()",
      text: "signum turns any distance into a single step" },
    { code: "me.attack(actor::THRUST);",
      text: "it thrusts" },
    { code: "self.pause = ATTACK_PAUSE;",
      text: "ATTACK_PAUSE after a thrust" },
  ],
},

{
  title: "What a hit does",
  codePath: "src/actor.rs",
  code: "    pub fn take_damage(&mut self, amount: u16) -> bool {\n        if self.invulnerable > 0 || self.invisible > 0 {\n            return false;\n        }\n        if self.barrier > 0 {\n            self.barrier = self.barrier.saturating_sub(amount);\n            return false;\n        }\n        self.hp = self.hp.saturating_sub(amount);\n        self.hits_taken = self.hits_taken.saturating_add(1);\n        self.invulnerable = self.mercy;\n        self.flash = FLASH_FRAMES;\n        self.player.set_white(true);\n        if self.hp == 0 {\n            // ...\n            self.select(anim::DELETED);\n            // ...\n        } else {\n            self.flinch();\n        }\n        true\n    }",
  text: "Every fighter, MegaMan or enemy, is damaged through this one function. First it checks whether the hit counts at all: a fighter still in its mercy period from the last hit, or made invisible by a chip, simply ignores it. A barrier chip soaks damage next, leaving health untouched. Otherwise health drops but never below zero, the mercy timer restarts (for MegaMan it lasts 120 frames, two seconds; enemies get none), and the sprite flashes white. At zero health the deleted animation starts, and the lines left out hand the fighter over to its dying routine; otherwise it flinches.",
  highlights: [
    { code: "self.invulnerable > 0",
      text: "mercy period" },
    { code: "self.barrier.saturating_sub(amount)",
      text: "A barrier chip soaks damage" },
    { code: "self.invulnerable = self.mercy",
      text: "the mercy timer restarts" },
    { code: "self.player.set_white(true)",
      text: "flashes white" },
    { code: "self.select(anim::DELETED)",
      text: "the deleted animation starts" },
  ],
},

{
  title: "Which slash Colonel swings",
  codePath: "src/ai.rs",
  code: "pub const CROSS_BASE: (i32, i32) = (2, 2); // provenance: derived -- dword_8103A04, asm31.s:158121\n// ...\nconst CROSS_SHAPES: [&[(i32, i32)]; 4] = [\n    &[(0, 0), (1, -1), (-1, 1)],\n    &[(0, 0), (-1, -1), (1, 1)],\n    &[(0, 0), (-1, -1), (-1, 1)],\n    &[(0, 0), (-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1)],\n];\n// ...\npub fn cross_targets(target: (i32, i32)) -> Option<&'static [(i32, i32)]> {\n    let rel = (target.0 - CROSS_BASE.0, target.1 - CROSS_BASE.1);\n    CROSS_SHAPES.iter().copied().find(|s| s.contains(&rel))\n}\n// ...\n                let spec = if cross_targets(target).is_some() {\n                    actor::CROSS\n                } else {\n                    actor::DIVIDE\n                };",
  text: "Colonel, a sword-carrying boss, has two slashes, and this picks one. The cross slash is aimed at a fixed panel: column two of the middle row, the centre of MegaMan's half. Four shapes are written as steps away from that panel; three are short diagonals and the last is a block of seven panels. The code measures where MegaMan stands from the centre and takes the first shape that covers him. If none does, Colonel uses the plain overhead slash. The skipped parts are notes on the tables and the waiting between attacks.",
  highlights: [
    { code: "(2, 2)",
      text: "column two of the middle row" },
    { code: "(-1, 1), (1, 1), (0, -1), (0, 1)",
      text: "a block of seven panels" },
    { code: "target.0 - CROSS_BASE.0, target.1 - CROSS_BASE.1",
      text: "measures where MegaMan stands" },
    { code: "find(|s| s.contains(&rel))",
      text: "the first shape that covers him" },
    { code: "actor::DIVIDE",
      text: "plain overhead slash" },
  ],
},

{
  title: "The chip file checks its own version",
  codePath: "src/chips.rs",
  code: "const MAGIC: &[u8; 4] = b\"BNCH\";\n// ...\nconst VERSION: u32 = 2; // canon: tools/chip_export.py's header field 0x04, \"u32 version (2; v2 appends a behavioural tail)\"\n// ...\nconst TAIL: usize = 8; // provenance: derived -- chip_export.py's own v2 append-only tail layout\n// ...\n    pub fn new(data: &'static [u8]) -> Self {\n        assert_eq!(&data[0..4], MAGIC, \"not a BNCH asset\");\n        let version = u32::from_le_bytes(data[4..8].try_into().unwrap());\n        assert_eq!(\n            version, VERSION,\n            \"chips.bin v1 read by v2 code: tail would be misread as behaviour\"\n        );\n        let count = u32::from_le_bytes(data[8..12].try_into().unwrap()) as usize;\n        // ...\n        let tail = data.len() - count * TAIL;\n        assert!(tail >= 12 + count * RECORD, \"BNCH asset without a v2 tail\");",
  text: "The list of chips lives in a file built into the game. It opens with four letters, BNCH, so the code knows it has the right file, then a version number, the second four bytes. A version 2 file ends with a tail of 8 bytes per chip describing how it behaves: its family, subfamily and parameters. The code finds that tail by counting back from the end of the file. An older file has no tail, so counting back would land in picture data and treat pixels as behaviour. The version check stops the game with a clear message instead. The skipped lines are notes saying so.",
  highlights: [
    { code: "b\"BNCH\"",
      text: "four letters, BNCH" },
    { code: "data[4..8]",
      text: "then a version number" },
    { code: "const TAIL: usize = 8;",
      text: "8 bytes per chip" },
    { code: "let tail = data.len() - count * TAIL;",
      text: "counting back from the end of the file" },
    { code: "\"chips.bin v1 read by v2 code: tail would be misread as behaviour\"",
      text: "stops the game with a clear message" },
  ],
},

{
  title: "The enemy's health shows once the fight begins",
  codePath: "src/battle.rs",
  code: "    fight_latch: bool,\n// ...\n        } else if self.intro_next < self.enemies.len() {\n            if !self.enemies[self.intro_next].is_present() {\n                self.enemies[self.intro_next].appear();\n            } else if !self.enemies[self.intro_next].is_busy() {\n                self.intro_next += 1;\n                // The last one has finished materialising: canon's handover\n                // writes 4 into oBattleState_Index_00 exactly here\n                // (sub_8007A0C, asm00_1.s:9716-9718) -- latch the fight\n                // state on (see fight_latch's doc).\n                if self.intro_next >= self.enemies.len() {\n                    self.fight_latch = true;\n                }\n// ...\n    fn hp_readout_live(&self) -> bool {\n        self.fight_latch && !matches!(self.seq.state, SEQ_0C | SEQ_10)\n    }",
  text: "Before a battle starts, the enemies appear one at a time. The code walks the enemy list: make the next one appear, wait until it has finished, move on. When the last one is done it sets fight_latch, a switch that stays on for the rest of the battle. At that same moment the real game writes 4, its number for \"fighting\", into its battle state. The health number under each enemy is drawn only while that switch is on, and stops once the battle is ending in a win or a loss. The skipped lines are the rest of the intro.",
  highlights: [
    { code: "self.enemies[self.intro_next].appear();",
      text: "make the next one appear" },
    { code: "self.fight_latch = true;",
      text: "a switch that stays on for the rest of the battle" },
    { code: "writes 4 into oBattleState_Index_00",
      text: "writes 4, its number for \"fighting\"" },
    { code: "fn hp_readout_live(&self) -> bool {",
      text: "The health number under each enemy" },
    { code: "SEQ_0C | SEQ_10",
      text: "ending in a win or a loss" },
  ],
},

{
  title: "A chip's pause before it works",
  codePath: "src/battle.rs",
  code: "if let Some((chip, left)) = self.presentation {\n    if left == 0 {\n        self.presentation = None;\n        match chip.id {\n            // ...\n            _ => {\n                if chip.family == BARRIER_FAMILY\n                    && chip.subfamily == BARRIER_SUBFAMILY\n                {\n                    self.megaman.set_barrier(barrier_hp(&chip));\n                    let mut bubble = spr::Player::new(spr::Assets::new(BARRIER), 0);\n                    // ...\n                    self.bubble = Some(bubble);\n                }\n            }\n        }\n    } else {\n        // ...\n        self.presentation = Some((chip, left - 1));\n    }\n}",
  text: "Some chips pause the fight before they act: time freezes and the chip's name shows. The presentation slot holds the chip and a countdown of the frames left. For Barrier the countdown starts at 45, about three quarters of a second. Each frame takes one off. At zero the slot empties and the chip acts. The code spots Barrier by its family and subfamily, two bytes in the chip's data that name the kind of attack, so Barr100 and Barr200 take the same path. The shield gets its HP and the bubble starts on its first animation, 0. Left out: the other chips, the bubble's colours, and the orbs one chip drops during the countdown.",
  highlights: [
    { code: "left - 1",
      text: "Each frame takes one off" },
    { code: "left == 0",
      text: "At zero the slot empties" },
    { code: "chip.subfamily == BARRIER_SUBFAMILY",
      text: "family and subfamily" },
    { code: "set_barrier(barrier_hp(&chip))",
      text: "The shield gets its HP" },
    { code: "spr::Assets::new(BARRIER), 0",
      text: "its first animation, 0" },
  ],
},

{
  title: "The background drifts on its own clock",
  codePath: "src/backdrop.rs",
  code: "pub fn update(&mut self, gfx: &Graphics) {\n    self.timer -= 1;\n    if self.timer == 0 {\n        self.entry = (self.entry + 1) % STEP_ORDER.len();\n        self.timer = STEP_HOLD[self.entry];\n        self.show_step(gfx, STEP_ORDER[self.entry]);\n    }\n\n    // ...\n    const BACKDROP_SCROLL_PERIOD_Q: u32 = 256 * 4; // provenance: derived -- canon's 256-px counter period in quarter-pixel units\n    self.x_q = (self.x_q + SCROLL_X_Q) % BACKDROP_SCROLL_PERIOD_Q;\n    self.y_q = (self.y_q + SCROLL_Y_Q) % BACKDROP_SCROLL_PERIOD_Q;\n    // ...\n    self.bg.set_scroll_pos((\n        -(((self.x_q + 3) / 4) as i32),\n        -(((self.y_q + 3) / 4) as i32),\n    ));\n}",
  text: "Behind the field, a patterned background slides slowly while its artwork changes. Two separate clocks run it. The first is a timer that goes down by one a frame. At zero the next picture shows, and the timer is reset to how long that picture stays. The second is the scroll, counted in quarter pixels. Each frame it moves half a pixel sideways and a quarter pixel up. It wraps at 256 * 4, which is 256 pixels, the width of the pattern. Adding 3 before dividing by 4 rounds up to whole pixels, and the minus signs move the pattern left and up. Left out: notes on where these numbers come from.",
  highlights: [
    { code: "self.timer -= 1",
      text: "a timer that goes down by one a frame" },
    { code: "STEP_HOLD[self.entry]",
      text: "how long that picture stays" },
    { code: "self.x_q + SCROLL_X_Q",
      text: "half a pixel sideways" },
    { code: "256 * 4",
      text: "256 * 4" },
    { code: "(self.x_q + 3) / 4",
      text: "Adding 3 before dividing by 4" },
  ],
},

{
  title: "BigBomb's blast covers its neighbours",
  codePath: "src/battle.rs",
  code: "wide: chip.family == BOMB_FAMILY_BLK_BIG\n    && chip.subfamily == BOMB_SUB_BIGBOMB,\n// ...\nlet spread: &[(i32, i32)] = if wide {\n    &[\n        (-1, -1),\n        (1, -1),\n        (0, -1),\n        (-1, 0),\n        (1, 0),\n        (0, 0),\n        (1, 1),\n        (-1, 1),\n        (0, 1),\n    ]\n} else {\n    &[(0, 0)]\n};\nfor (dc, dr) in spread {\n    let (c, r) = (col + dc, row + dr);",
  text: "When a bomb lands, it damages the panel under it. BigBomb also hits all eight panels around that one. The code tells which bomb this is from two bytes in the chip's data, its family and subfamily. Only BigBomb has this pair, so only BigBomb is marked as a wide bomb. On landing, the spread list holds moves of -1, 0 or 1 columns and rows from where the bomb fell. A normal bomb's list is only (0, 0), the landing panel itself. Each move is added to the landing spot. Left out: the bomb's other settings, such as its flight time, and the landing code in between.",
  highlights: [
    { code: "chip.subfamily == BOMB_SUB_BIGBOMB",
      text: "family and subfamily" },
    { code: "if wide {",
      text: "marked as a wide bomb" },
    { code: "(-1, -1)",
      text: "-1, 0 or 1 columns and rows" },
    { code: "&[(0, 0)]",
      text: "only (0, 0)" },
    { code: "(col + dc, row + dr)",
      text: "added to the landing spot" },
  ],
},

{
  title: "The full gauge flows",
  codePath: "src/hudtiles.rs",
  code: "        let ready = lit >= BAR_CELLS;\n        // A full bar flows; anything less stands still, so the animation only\n        // runs while it is full and starts over each time it fills.\n        if ready {\n            self.gauge_tick = self.gauge_tick.wrapping_add(1);\n        } else {\n            self.gauge_tick = 0;\n// ...\n        let full_state: Option<(u16, u16)> = if ready {\n            Some((\n                BAR_CYCLE[((self.gauge_tick / BAR_FRAMES) % BAR_CYCLE.len() as u32) as usize],\n                if self.gauge_tick & 8 != 0 {\n                    MARKER_READY\n                } else {\n                    MARKER_WAITING\n                },\n            ))",
  text: "The custom gauge at the top of the screen is a row of square tiles, twelve of them in the bar, and lit counts how many are filled. Once all twelve are lit the bar flows, not by changing colours but by swapping between four slightly shifted tile pictures, each held for seven frames. A counter climbs by one every frame the bar stays full and restarts at zero when it is not. The same counter blinks the marker beside the bar: its part worth 8 turns on and off every eight frames, flipping the marker between cyan and orange. The skipped lines close the counter's branch and hold notes.",
  highlights: [
    { code: "let ready = lit >= BAR_CELLS;",
      text: "Once all twelve are lit" },
    { code: "(self.gauge_tick / BAR_FRAMES) % BAR_CYCLE.len() as u32",
      text: "four slightly shifted tile pictures" },
    { code: "self.gauge_tick = self.gauge_tick.wrapping_add(1);",
      text: "climbs by one every frame" },
    { code: "self.gauge_tick = 0;",
      text: "restarts at zero" },
    { code: "self.gauge_tick & 8 != 0",
      text: "its part worth 8" },
  ],
},

{
  title: "The health number walks to its new value",
  codePath: "src/hud.rs",
  code: "    /// One frame of catching up to `actual`.\n    pub fn update(&mut self, actual: u16) {\n        self.flash = self.flash.saturating_sub(1);\n        if self.shown == actual {\n            return;\n        }\n        // ...\n        let (set, flash) = if actual < self.shown {\n            (SET_DAMAGE, 15)\n        } else {\n            (SET_HEAL, 1)\n        };\n        self.set = set;\n        self.flash = self.flash.max(flash);\n        // ...\n        let step = self.shown.abs_diff(actual) / HP_WALK_DIVISOR + HP_WALK_MIN_STEP;\n        self.shown = if actual < self.shown {\n            self.shown.saturating_sub(step).max(actual)\n        } else {\n            (self.shown + step).min(actual)\n        };\n    }",
  text: "The health box does not jump straight to a new value. Once a frame, update compares the number on screen with the real health. If they differ, the digits switch colour: the damage colours are held for 15 frames, a quarter of a second, while the healing colours last one frame. Then the shown number moves by the gap divided by eight, plus four, never overshooting, so a drop from 60 health to 50 reads 55, then 51, then the target. The left-out lines are comments and the two named constants, eight and four.",
  highlights: [
    { code: "if self.shown == actual",
      text: "compares the number on screen with the real health" },
    { code: "(SET_DAMAGE, 15)",
      text: "damage colours are held for 15 frames" },
    { code: "(SET_HEAL, 1)",
      text: "healing colours last one frame" },
    { code: "/ HP_WALK_DIVISOR + HP_WALK_MIN_STEP",
      text: "the gap divided by eight, plus four" },
    { code: ".max(actual)",
      text: "never overshooting" },
  ],
},

{
  title: "Only the panels that changed are repainted",
  codePath: "src/field.rs",
  code: "fn index(col: i32, row: i32) -> usize {\n    (row as usize - 1) * COLS as usize + (col as usize - 1)\n}\n// ...\n    pub fn update(&mut self, occupied: u32) {\n        for i in 0..PANEL_COUNT {\n            let bit = 1 << i;\n            // ...\n            if anim != self.animation[i] {\n                self.animation[i] = anim;\n                self.dirty |= bit;\n            }\n        }\n        // ...\n    }\n\n    pub fn take_dirty(&mut self) -> u32 {\n        core::mem::take(&mut self.dirty)\n    }",
  text: "Redrawing the whole field every frame would waste time, so the field keeps a checklist packed into one number, a bit per panel. index numbers the eighteen panels row by row, starting from zero at the top left, and bit i of the checklist stands for panel i. Each frame, update works out what every panel should look like; the left-out lines are the cracking, breaking and blinking rules. When the look changes, it switches that panel's bit on in dirty. The drawing code calls take_dirty, which hands over the checklist and leaves zero behind, then repaints only the marked panels.",
  highlights: [
    { code: "(row as usize - 1) * COLS as usize + (col as usize - 1)",
      text: "numbers the eighteen panels row by row" },
    { code: "let bit = 1 << i;",
      text: "bit i of the checklist stands for panel i" },
    { code: "if anim != self.animation[i]",
      text: "When the look changes" },
    { code: "self.dirty |= bit;",
      text: "switches that panel's bit on" },
    { code: "core::mem::take(&mut self.dirty)",
      text: "leaves zero behind" },
  ],
},

{
  title: "Reading a chip's record",
  codePath: "src/chips.rs",
  code: "    pub fn get(&self, index: usize) -> Chip {\n        assert!(index < self.count);\n        let r = &self.data[12 + index * RECORD..12 + (index + 1) * RECORD];\n        // ...\n        let (icon, picture, len, palette) = (u32_at(20), u32_at(24), u32_at(28), u32_at(32));\n        Chip {\n            id: u16_at(0),\n            element: r[2],\n            mb: r[3],\n            power: u16_at(4),\n            codes: r[6..10].try_into().unwrap(),\n            name: r[10..19].try_into().unwrap(),\n            // ...\n            palette: &self.data[palette..palette + 32],\n            // ...\n        }\n    }",
  text: "Every battle chip has a same-sized record in one data file. get finds one by skipping the file's 12-byte header, which holds a label, a version and a count, then one whole record for each chip before it. Inside, each field sits at a fixed place: the id, the element, the folder cost, attack power, the four code letters it can come in and a name of up to nine letters. Four more numbers say where its pictures sit; the palette is 32 bytes, sixteen colours of two bytes each. Left out: the byte readers, icon, card art and behaviour bytes.",
  highlights: [
    { code: "12 + index * RECORD",
      text: "skipping the file's 12-byte header" },
    { code: "power: u16_at(4)",
      text: "attack power" },
    { code: "codes: r[6..10]",
      text: "the four code letters" },
    { code: "name: r[10..19]",
      text: "a name of up to nine letters" },
    { code: "palette + 32",
      text: "sixteen colours of two bytes each" },
  ],
},

{
  title: "Chips that share a family",
  codePath: "src/battle.rs",
  code: "if let Some((chip, left)) = self.presentation {\n    if left == 0 {\n        self.presentation = None;\n        match (chip.family, chip.subfamily) {\n            // ...\n            (BARRIER_FAMILY, INVISIBL_SUBFAMILY) => {\n                self.megaman.set_invisible(chip.params[0] as u16)\n            }\n            // ...\n            (BARRIER_FAMILY, AREAGRAB_SUBFAMILY) => {}\n            // ...\n            (BARRIER_FAMILY, BARRIER_SUBFAMILY) => {\n                self.megaman.set_barrier(barrier_hp(&chip));\n                let mut bubble = spr::Player::new(spr::Assets::new(BARRIER), 0);\n                bubble.set_offsets_follow_shift(true);\n                bubble.set_palette_add(barrier_palette(&chip));\n                self.bubble = Some(bubble);\n            }",
  text: "Every chip has a record: a few bytes describing its attack. Two of them are the family, a broad group, and the subfamily, the variant inside that group. Invisibl, AreaGrab and the Barriers share one family, so when the chip's short showing-off pause ends, this code picks the behaviour from that pair. Invisibl takes how long to stay hidden from its record's first parameter. AreaGrab does nothing here, because its falling orbs already took their panels. A Barrier gives MegaMan a shield and draws the bubble. The three left-out lines are comments naming each case.",
  highlights: [
    { code: "match (chip.family, chip.subfamily)",
      text: "the family, a broad group" },
    { code: "chip.params[0]",
      text: "record's first parameter" },
    { code: "(BARRIER_FAMILY, AREAGRAB_SUBFAMILY) => {}",
      text: "AreaGrab does nothing here" },
    { code: "self.megaman.set_barrier(barrier_hp(&chip));",
      text: "gives MegaMan a shield" },
    { code: "self.bubble = Some(bubble);",
      text: "draws the bubble" },
  ],
},

{
  title: "AirShot pushes its target back",
  codePath: "src/battle.rs",
  code: "if chip.family == AIRSHOT_FAMILY {\n    let (fc, fr) = self.megaman.front_panel();\n    let blocked = self\n        .enemies\n        .iter()\n        .fold(self.megaman.occupancy(), |m, e| m | e.occupancy())\n        | self.panels.other_half(true);\n    for enemy in self.enemies.iter_mut().filter(|e| e.is_targetable()) {\n        if enemy.panel() == (fc, fr) && enemy.take_damage(chip.power) {\n            enemy.hop(dx, 0, blocked);\n        }\n    }\n    return;\n}",
  text: "AirShot is a gust that shoves what it hits. When the chip strikes, the code finds the panel directly in front of MegaMan. It then marks the squares nothing may move into: any panel MegaMan or an enemy stands on, plus the half of the field that belongs to MegaMan. Each enemy that can be hit and stands on that front panel takes the chip's power as damage, and if the hit counted it hops one panel further away, unless a marked square is in the way. The chip is recognised by its family byte, the number in its record saying what kind of attack it is.",
  highlights: [
    { code: "chip.family == AIRSHOT_FAMILY",
      text: "its family byte" },
    { code: "self.megaman.front_panel()",
      text: "the panel directly in front of MegaMan" },
    { code: "| self.panels.other_half(true)",
      text: "the half of the field that belongs to MegaMan" },
    { code: "enemy.take_damage(chip.power)",
      text: "takes the chip's power as damage" },
    { code: "enemy.hop(dx, 0, blocked)",
      text: "hops one panel further away" },
  ],
},

{
  title: "The timer after a flinch",
  codePath: "src/actor.rs",
  code: "Action::Flinching { .. } => {\n    self.select(anim::IDLE);\n    // ...\n    self.phase_arm_shadow = SENTINEL_FRAMES + PHASE_ARM_FRAMES;\n    Action::Idle\n}\n// ...\nAction::Flinching { ticks } => (*ticks as u16),\n_\n    if self.phase_arm_shadow > 0\n        && matches!(self.action, Action::Idle) =>\n{\n    if self.phase_arm_shadow == SENTINEL_FRAMES + PHASE_ARM_FRAMES {\n        TIMER_SENTINEL // canon: flinch underflow frame, asm00_2.s:18353-18355 (see `phase_arm_shadow`)\n    } else {\n        (self.phase_arm_shadow - SENTINEL_FRAMES) as u16\n    }\n}",
  text: "When MegaMan is hit, the flinch counts down on a timer stored with MegaMan. The real game keeps using that timer afterwards: on the first frame after the flinch it reads 0xffff, a marker meaning the count ran out, then it counts 9 down to 0, one per frame. The port copies this only so a test can compare its numbers with the real game's; nothing in play reads it. Leaving the flinch arms a countdown of eleven frames, one marker frame plus ten counting ones. The first left-out line is a comment; the second skips to the code that reports numbers to the test.",
  highlights: [
    { code: "Action::Flinching { ticks } => (*ticks as u16)",
      text: "the flinch counts down on a timer" },
    { code: "TIMER_SENTINEL",
      text: "a marker meaning the count ran out" },
    { code: "(self.phase_arm_shadow - SENTINEL_FRAMES) as u16",
      text: "counts 9 down to 0" },
    { code: "self.phase_arm_shadow = SENTINEL_FRAMES + PHASE_ARM_FRAMES;",
      text: "arms a countdown of eleven frames" },
  ],
},

{
  title: "Going invisible",
  codePath: "src/actor.rs",
  code: "pub fn set_invisible(&mut self, frames: u16) {\n    self.invisible = frames;\n}\n// ...\npub fn take_damage(&mut self, amount: u16) -> bool {\n    if self.invulnerable > 0 || self.invisible > 0 {\n        return false;\n    }\n    // ...\n}\n// ...\n    self.invisible = self.invisible.saturating_sub(1);\n// ...\n    if self.invisible & INVIS_HIDE_BIT != 0 {\n        return;\n    }",
  text: "Invisibl makes MegaMan impossible to hit for a while. When the chip's opening pause ends, the fight calls set_invisible with a frame count read from the chip's own record: 104 frames, a little under two seconds at sixty a second. Each frame the counter drops by one. While it is above zero, take_damage refuses the hit. When drawing, the code tests INVIS_HIDE_BIT, the bit of the counter worth 2; while it is set the body is skipped, so MegaMan flickers, two frames gone and two shown. The gaps skip the rest of the damage code and the drawing.",
  highlights: [
    { code: "set_invisible",
      text: "set_invisible" },
    { code: "self.invisible > 0",
      text: "above zero" },
    { code: "return false;",
      text: "refuses the hit" },
    { code: "self.invisible.saturating_sub(1)",
      text: "drops by one" },
    { code: "INVIS_HIDE_BIT",
      text: "INVIS_HIDE_BIT" },
  ],
},

{
  title: "A barrier soaks up hits",
  codePath: "src/battle.rs",
  code: "const BARRIER_HP_BY_PARAM: [u16; 8] = [\n    0, 0x000A, 0, 0, 0, 0x0064, 0, 0x00C8,\n];\n// ...\n(BARRIER_FAMILY, BARRIER_SUBFAMILY) => {\n    self.megaman.set_barrier(barrier_hp(&chip));\n    let mut bubble = spr::Player::new(spr::Assets::new(BARRIER), 0);\n    bubble.set_offsets_follow_shift(true);\n    bubble.set_palette_add(barrier_palette(&chip));\n    self.bubble = Some(bubble);\n}\n// ...\nif let Some(bubble) = self.bubble.as_mut() {\n    bubble.update();\n    if self.megaman.barrier() == 0 {\n        self.bubble = None;\n    }\n}",
  text: "Barrier, Barr100 and Barr200 are one chip at three strengths. The chip's first parameter picks a slot in BARRIER_HP_BY_PARAM: one slot holds 10 hit points (written 0x000A), others 100 and 200, and unused slots stay zero. When the chip's pause ends, set_barrier gives MegaMan that many barrier points, and a bubble sprite appears, tinted teal, gold or pink by barrier_palette. Hits drain the barrier instead of his health. Every frame the bubble animates, and once the barrier is empty the bubble is dropped. The gaps hide the small lookup functions and the colour table.",
  highlights: [
    { code: "BARRIER_HP_BY_PARAM",
      text: "BARRIER_HP_BY_PARAM" },
    { code: "0x000A",
      text: "10 hit points (written 0x000A)" },
    { code: "set_barrier(",
      text: "set_barrier" },
    { code: "barrier_palette(&chip)",
      text: "barrier_palette" },
    { code: "self.bubble = None;",
      text: "the bubble is dropped" },
  ],
},

{
  title: "AreaGrab's orbs fall and burst",
  codePath: "src/battle.rs",
  code: "let mut areagrab_landed = false;\nfor orb in self.areagrab_orbs.iter_mut() {\n    if orb.burst {\n        orb.player.update();\n    } else if orb.landed {\n        orb.burst = true;\n        orb.player.play(AREAGRAB_BURST_ANIM);\n    } else {\n        orb.z -= AREAGRAB_ORB_ZVEL;\n        if orb.z <= 0 {\n            orb.z = 0;\n            orb.landed = true;\n            areagrab_landed = true;\n        }\n    }\n    // ...\n}",
  text: "AreaGrab takes a column of the enemy's panels by dropping an orb onto each of its three rows. Each orb carries a height, z. Every frame this loop lowers it by AREAGRAB_ORB_ZVEL, eight pixels, from 256 pixels up, so the fall lasts 32 frames, about half a second. When z reaches zero the orb is marked landed, and a flag notes that one came down. The next frame it starts its burst animation, and after that it only plays it out. The left-out line cycles the orb's colours; once the flag is set, the column changes owner.",
  highlights: [
    { code: "orb.z -= AREAGRAB_ORB_ZVEL;",
      text: "AREAGRAB_ORB_ZVEL" },
    { code: "if orb.z <= 0",
      text: "When z reaches zero" },
    { code: "orb.landed = true;",
      text: "marked landed" },
    { code: "areagrab_landed = true;",
      text: "a flag notes that one came down" },
    { code: "orb.player.play(AREAGRAB_BURST_ANIM);",
      text: "burst animation" },
  ],
},

{
  title: "The health box is built from tile pairs",
  codePath: "src/hudtiles.rs",
  code: "    pub fn set_hp(&mut self, bg: &mut RegularBackground, hp: u16) {\n        // ...\n        let base = self.hp_col();\n        // The right cap is the left one MIRRORED, as the real ROM's map has\n        // it: same tile pair with h-flip set.\n        self.cell_flipped(bg, base, CAP_PAIR, false);\n        self.cell_flipped(bg, base + 1 + SLOTS, CAP_PAIR, true);\n        let mut left = hp;\n        for slot in (0..SLOTS).rev() {\n            let pair = if left == 0 && slot + 1 != SLOTS {\n                BLANK_PAIR\n            } else {\n                (left % 10) as u16\n            };\n            left /= 10;\n            self.cell(bg, base + 1 + slot, pair);\n        }\n    }",
  text: "The health box in the top corner is a row of background tiles. A tile is a square of art eight pixels on a side, and each column of the box is two tiles stacked. The box is a cap, four digit slots, then the same cap drawn mirrored. The loop fills the slots right to left, taking the last digit with left % 10, the remainder after dividing by ten. Once the number runs out, the leading slots get a blank pair, so a health of 60 shows as blank, blank, six, zero. Left out: a check that skips the repaint when the number has not changed.",
  highlights: [
    { code: "CAP_PAIR, true",
      text: "the same cap drawn mirrored" },
    { code: "for slot in (0..SLOTS).rev()",
      text: "fills the slots right to left" },
    { code: "left % 10",
      text: "left % 10" },
    { code: "BLANK_PAIR",
      text: "a blank pair" },
  ],
},

{
  title: "Picking the face in the corner",
  codePath: "src/emotion.rs",
  code: "        let slot = usize::from(emotion);\n        let face = if slot < FACE_SLOTS {\n            FACE_INDEX[slot] as usize\n        } else {\n            FACE_INDEX[0] as usize\n        };\n\n        // ...\n        let pal = slot * 32;\n        // ...\n        let left = &bank[face..face + LEFT_HALF_LEN];\n        let right = &bank[RIGHT_HALF.0..RIGHT_HALF.0 + RIGHT_HALF.1];\n        let split = WIDE_TILES * 32;\n        Self {\n            wide: Some(DynamicSprite16::from_bytes(Size::S32x16, &left[..split]).to_vram(palette.clone())),\n            narrow: Some(DynamicSprite16::from_bytes(Size::S16x16, right).to_vram(palette)),\n        }",
  text: "The portrait at the top left shows MegaMan's mood. It is two sprites: a wide one 32 pixels across and 16 tall, and a 16-pixel square beside it. The mood number picks an entry of FACE_INDEX, 23 starting points in one block of face art; a number past the end falls back to the calm first face. Each mood has its own 16 colours, found at slot * 32 because a colour takes two bytes. Only the wide piece changes: the square is the same art for every face. Left out: a note on the original game's code, and the colour-copying loop.",
  highlights: [
    { code: "FACE_INDEX[slot]",
      text: "FACE_INDEX" },
    { code: "FACE_INDEX[0]",
      text: "falls back to the calm first face" },
    { code: "slot * 32",
      text: "slot * 32" },
    { code: "Size::S32x16",
      text: "a wide one 32 pixels across and 16 tall" },
    { code: "RIGHT_HALF.0..RIGHT_HALF.0 + RIGHT_HALF.1",
      text: "the square is the same art for every face" },
  ],
},

{
  title: "The test leaves a note in memory",
  codePath: "src/fixture.rs",
  code: "pub fn read() -> Option<Fixture> {\n    unsafe {\n        if r32(0) != MAGIC {\n            return None;\n        }\n        // ...\n        Some(Fixture {\n            enemies: r8(4),\n            enemy_kind: r8(5),\n            enemy_col: r8(6),\n            enemy_row: r8(7),\n            megaman_hp: r16(8),\n            megaman_col: r8(10),\n            megaman_row: r8(11),\n            hand_count: r8(12),\n            hand,\n            gauge: r8(18),\n            flags: SceneFlags::from(r8(19)),",
  text: "To check this game against the original, a test has to start it in an exact situation: which enemies, how much health MegaMan has, which chips are in hand. The test writes a short note, 64 bytes long, into a fixed spot in the console's memory. read first compares the note's opening four bytes against MAGIC, the letters FIXT. Without them it returns None and the game plays normally. Otherwise each field comes from its own place in the note: r8(4) is the one byte at position 4, the enemy count, and r16(8) is two bytes, MegaMan's health. Left out is gathering the hand's chips and a few more lists.",
  highlights: [
    { code: "if r32(0) != MAGIC {",
      text: "compares the note's opening four bytes against MAGIC" },
    { code: "return None;",
      text: "it returns None" },
    { code: "enemies: r8(4),",
      text: "r8(4) is the one byte at position 4, the enemy count" },
    { code: "megaman_hp: r16(8),",
      text: "r16(8) is two bytes, MegaMan's health" },
    { code: "// ...",
      text: "Left out is gathering the hand's chips" },
  ],
},

{
  title: "One number per chip, and the gaps close up",
  codePath: "src/deck.rs",
  code: "    /// Pack a chip and its code letter (0 = A) the way the folder does.\n    pub const fn entry(id: u16, code: u8) -> u16 {\n        id | (code as u16) << 9\n    }\n\n    pub const fn id(entry: u16) -> u16 {\n        entry & 0x1ff\n    }\n\n    // ...\n\n    /// Pack the live chips to the front, as opening the window does.\n    pub fn compact(&mut self) {\n        let mut next = 0;\n        for i in 0..FOLDER_SIZE {\n            if self.chips[i] != EMPTY {\n                self.chips.swap(i, next);\n                next += 1;\n            }\n        }\n    }",
  text: "The folder stores each chip as a single number made of on-off digits called bits. The lowest nine bits say which chip it is. The chip's code letter (A is stored as 0) decides which chips can be picked together. It is moved up past those bits with << 9, so the two never overlap. Masking with 0x1ff, nine bits all on, gets the chip back out. Left out are the matching step for the letter, and the shuffle. When the chip window opens, compact walks the folder's thirty slots and slides every chip still there to the front in order, so the used-up gaps gather at the end.",
  highlights: [
    { code: "id | (code as u16) << 9",
      text: "moved up past those bits with << 9" },
    { code: "entry & 0x1ff",
      text: "Masking with 0x1ff, nine bits all on" },
    { code: "// ...",
      text: "Left out are" },
    { code: "for i in 0..FOLDER_SIZE {",
      text: "walks the folder's thirty slots" },
    { code: "self.chips.swap(i, next);",
      text: "slides every chip still there to the front" },
  ],
},

{
  title: "Fire beats wood, wood beats electric",
  codePath: "src/battle.rs",
  code: "fn damage_element_mult(chip_element: u8, def_elem: u8, def_weakness: u8) -> u32 {\n    let (atk_primary, atk_bits) = match chip_element {\n        0 => (1u8, 0u8),\n        1 => (2, 0),\n        // ...\n        5 => (0, 0x80),\n    // ...\n        match (def_elem, atk_primary) {\n            (1, 2) => 1, // def=HEAT weak to AQUA.\n            (2, 3) => 1, // def=AQUA weak to ELEC.\n            (3, 4) => 1, // def=ELEC weak to WOOD.\n            (4, 1) => 1, // def=WOOD weak to HEAT.\n            _ => 0,\n        }\n    // ...\n    let secondary_hit: u32 =\n        if def_weakness != 0 && (def_weakness & atk_bits) != 0 { 1 } else { 0 };\n    // ...\n    1 + primary_hit + secondary_hit\n}",
  text: "Chips and enemies can carry an element. This function turns a hit into a damage multiplier. First the chip's element is translated: fire, the chip's element 0, becomes heat, the game's element 1, while a sword chip becomes a single on/off flag. A short list of pairs then says who beats whom: a heat enemy is weak to aqua, aqua to electric, electric to wood, wood to heat. A second check compares the flag with the enemy's extra weaknesses. Each match adds one, giving 1, 2 or 3 times the damage. Left out are other elements and a range check.",
  highlights: [
    { code: "0 => (1u8, 0u8)",
      text: "fire, the chip's element 0, becomes heat, the game's element 1" },
    { code: "5 => (0, 0x80)",
      text: "a sword chip becomes a single on/off flag" },
    { code: "(1, 2) => 1, // def=HEAT weak to AQUA.",
      text: "a heat enemy is weak to aqua" },
    { code: "(def_weakness & atk_bits)",
      text: "extra weaknesses" },
    { code: "1 + primary_hit + secondary_hit",
      text: "1, 2 or 3 times the damage" },
  ],
},

{
  title: "Turning a panel to poison",
  codePath: "src/field.rs",
  code: "const PANEL_POISON_MASK: u32 = 0x3f5f; // canon: dword_800CBD0, object.s:2561\nconst PANEL_POISON_TEMPLATE: u32 = 0x114; // canon: off_800CBD4, object.s:2563\n// ...\n        if panel_type == PANEL_POISON && !self.poison(i) {\n            // ...\n            return;\n        }\n// ...\n    fn poison(&mut self, i: usize) -> bool {\n        if self.flags[i] & panel_flags::GUARD_10 == 0 {\n            return false;\n        }\n        self.flags[i] = (self.flags[i] & !PANEL_POISON_MASK) | PANEL_POISON_TEMPLATE;\n        self.types[i] = PANEL_POISON as u8;\n        true\n    }",
  text: "Each panel of the field keeps a flags word: many on/off switches packed into one number. Turning a panel to poison runs through this routine. It first checks the switch named GUARD_10, which only whole panels have; for a hole or a broken panel the request is quietly dropped. Otherwise the mask 0x3f5f picks out the switches to wipe, the template 0x114 is the poison panel's own set of switches, and the panel's type becomes poison, which decides how it is drawn. Left out are a note about the refusal and the plain path every other panel type takes.",
  highlights: [
    { code: "panel_flags::GUARD_10",
      text: "GUARD_10" },
    { code: "return false;",
      text: "quietly dropped" },
    { code: "PANEL_POISON_MASK: u32 = 0x3f5f",
      text: "mask 0x3f5f" },
    { code: "PANEL_POISON_TEMPLATE: u32 = 0x114",
      text: "template 0x114" },
    { code: "self.types[i] = PANEL_POISON as u8;",
      text: "type becomes poison" },
  ],
},

{
  title: "A cross form is a change of colours",
  codePath: "src/battle.rs",
  code: "fn cross_form_palette_row(transformation: usize) -> usize {\n    const CROSS_FORM_PALETTE_ROW: [usize; 11] =\n        [0x0, 0x2, 0x7, 0x9, 0xd, 0x13, 0x5, 0x11, 0xb, 0xf, 0x15]; // provenance: derived -- canon byte_80203EA @0x080203EA (ROM bytes, T135 A/B: TF_HEATCROSS -> row 2 measured in OBJ bank 0)\n    CROSS_FORM_PALETTE_ROW\n        .get(transformation)\n        .copied()\n        .unwrap_or(0)\n}\n// ...\n        let transformation = unsafe {\n            (NAVISTATS_TRANSFORMATION_ADDR as *const u8).read_volatile()\n        } as usize;\n        megaman.set_form_palette_row(cross_form_palette_row(transformation));",
  text: "A cross form is MegaMan transformed, borrowing a partner's powers and look. The game keeps no second body for it: it draws the same pieces with a different palette, the short list of colours a picture's pixels point into. At battle setup the code reads one byte from MegaMan's stats in memory saying which form is active, and looks it up among eleven palette rows, one per form. Plain MegaMan, form 0, keeps row 0; Heat Cross, form 1, takes row 2. Anything past the list falls back to row 0. The rest of setup is left out.",
  highlights: [
    { code: "[usize; 11]",
      text: "eleven palette rows" },
    { code: "read_volatile()",
      text: "reads one byte" },
    { code: "[0x0, 0x2,",
      text: "Heat Cross, form 1, takes row 2" },
    { code: ".unwrap_or(0)",
      text: "falls back to row 0" },
    { code: "megaman.set_form_palette_row",
      text: "different palette" },
  ],
},

{
  title: "The cannon chips share one branch",
  codePath: "src/battle.rs",
  code: "const CANNON_FAMILY: u8 = 0x14; // canon: ChipDataArr_8021DA8 AttackFamily +0xb of ids 1/2/3 (data/ChipDataArr.s:43/74/105)\n// ...\n_ if chip.family == CANNON_FAMILY => {\n    self.chip_in_use = Some(chip);\n    self.megaman.attack(CANNON);\n    // ...\n    let (mc, mr) = self.megaman.panel();\n    let (mx, my) = field::panel_centre(mc, mr);\n    let mut barrel = spr::Player::new(spr::Assets::new(BARREL_CHARGE), 0);\n    // byte_80B8BD4 rows 0-2: the same barrel with palette 0, 1\n    // and 2 for Cannon, HiCannon and M-Cannon.\n    barrel.set_palette_add(chip.subfamily as usize);\n    self.effects\n        .push((barrel, (mx + CANNON_BARREL_DX, my - CANNON_BARREL_DY), CANNON_FRAMES, false, false));\n}",
  text: "Every chip's record carries a family number that says what kind of attack it is. Cannon, HiCannon and M-Cannon all carry family 0x14, so one branch handles all three. It starts MegaMan's cannon pose, then puts a barrel picture on his arm, 16 pixels forward and 24 up from the middle of his panel. The only difference is colour: the subfamily, a second number that is 0, 1 or 2, picks which of three palettes (sets of colours) paints the barrel. Skipped: the code between the number and the branch, and a note on the barrel's animation.",
  highlights: [
    { code: "chip.family == CANNON_FAMILY",
      text: "family 0x14" },
    { code: "self.megaman.attack(CANNON)",
      text: "cannon pose" },
    { code: "mx + CANNON_BARREL_DX, my - CANNON_BARREL_DY",
      text: "16 pixels forward and 24 up" },
    { code: "barrel.set_palette_add(chip.subfamily as usize)",
      text: "picks which of three palettes" },
  ],
},

{
  title: "Reading the reward after a battle",
  codePath: "src/battle.rs",
  code: "/// display by sub_802C54C (asm03_0.s:12691): 0xFFFF = no reward;\n/// bits 15-14 clear = a CHIP reward (id = word >> 9, count = word &\n/// 0x1FF) -- not this pair's number, None here; bits 15-14 set = the\n/// amount in word & 0x3FFF (drawn by revealResultReward_802C044's\n/// chain, asm03_0.s:11963).\n// ...\nfn battle_zenny(&self) -> Option<u16> {\n    let w = self.reward_word;\n    if w == RESULT_REWARD_NONE || w >> 14 == 0 {\n        None\n    } else {\n        Some(w & 0x3FFF) // canon: sub_802C54C's amount mask (asm03_0.s:12705-12706 lsl/lsr #0x12; 12791-12793 is sub_802C5E6, the BCD display path)\n    }\n}",
  text: "After a battle the results screen shows a reward: either some zenny, the game's money, or a chip. The game keeps the reward in one 16-bit word, a number made of sixteen on/off bits, and the top two bits say which kind it is. 0xFFFF, every bit on, means no reward. Shifting right by 14 places leaves only the top two bits. If both are off, it is a chip, and this function returns None. Otherwise the mask 0x3FFF keeps the lower fourteen bits, which hold the amount. Skipped: a note saying the roll that fills the word is not written yet.",
  highlights: [
    { code: "self.reward_word",
      text: "one 16-bit word" },
    { code: "w == RESULT_REWARD_NONE",
      text: "every bit on, means no reward" },
    { code: "w >> 14 == 0",
      text: "leaves only the top two bits" },
    { code: "Some(w & 0x3FFF)",
      text: "keeps the lower fourteen bits" },
  ],
},

];
