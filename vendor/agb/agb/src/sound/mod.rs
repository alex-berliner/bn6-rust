//! # Game Boy Advance audio
//!
//! The [`mixer`](crate::sound::mixer) module is high performance, and allows for playing wav files at
//! various levels of quality. Check out the module documentation for more.
//!
//! The [`psg`](crate::sound::psg) module is a much smaller thing: direct access to the four
//! classic Game Boy sound channels, which run entirely in hardware once fired.
pub mod mixer;
pub mod psg;
