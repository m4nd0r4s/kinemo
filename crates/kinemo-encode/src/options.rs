#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Format {
    Mp4,
    Webm,
    Mov,
    Gif,
}

impl Format {
    /// Guess the format from a file extension (case-insensitive).
    pub fn from_extension(ext: &str) -> Option<Format> {
        match ext.to_ascii_lowercase().as_str() {
            "mp4" | "m4v" => Some(Format::Mp4),
            "webm" => Some(Format::Webm),
            "mov" => Some(Format::Mov),
            "gif" => Some(Format::Gif),
            _ => None,
        }
    }

    /// Whether the container/codec combination can carry an alpha channel.
    pub fn supports_alpha(self) -> bool {
        !matches!(self, Format::Mp4)
    }
}

/// An audio file placed on the timeline.
#[derive(Clone, Debug, PartialEq)]
pub struct AudioClip {
    pub path: String,
    /// Start time in seconds on the video timeline.
    pub start: f64,
    /// Linear gain (1.0 = unchanged).
    pub gain: f64,
}

#[derive(Clone, Debug, PartialEq)]
pub struct EncoderOptions {
    pub width: u32,
    pub height: u32,
    pub fps: f64,
    pub format: Format,
    /// Keep the alpha channel (WebM, MOV; GIF uses 1-bit transparency). Ignored for MP4.
    pub transparent: bool,
    /// Quality override; defaults per format (MP4 18, WebM 31). Unused for MOV/GIF.
    pub crf: Option<u32>,
    pub audio: Vec<AudioClip>,
    /// Total duration in seconds; audio is trimmed to it.
    pub duration: f64,
}

impl EncoderOptions {
    pub fn frame_len(&self) -> usize {
        self.width as usize * self.height as usize * 4
    }
}
