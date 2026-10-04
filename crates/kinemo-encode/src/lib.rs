//! Video encoding by piping raw RGBA frames into an `ffmpeg` subprocess.
//!
//! The binary is located through `KINEMO_FFMPEG`, then `PATH`, then common
//! install locations. Arguments are chosen for byte-for-byte reproducible
//! output (bitexact flags, fixed thread counts, stripped metadata).

mod audio;
mod encoder;
mod error;
mod ffmpeg;
mod formats;
mod options;

pub use encoder::VideoEncoder;
pub use error::EncodeError;
pub use ffmpeg::{ffmpeg_available, find_ffmpeg};
pub use options::{AudioClip, ClipRole, EncoderOptions, Format};
