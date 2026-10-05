//! Video encoding by piping raw frames (YUV 4:2:0 for MP4, RGBA otherwise) into an `ffmpeg`
//! subprocess.
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
mod pixels;

pub use encoder::VideoEncoder;
pub use error::EncodeError;
pub use ffmpeg::{ffmpeg_available, find_ffmpeg};
pub use options::{AudioClip, ClipRole, EncoderOptions, Format, InputFormat};
pub use pixels::rgba_to_yuv420;
