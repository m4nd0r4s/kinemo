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

/// What a clip is in the mix.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum ClipRole {
    /// Narration: music ducks under it.
    Voice,
    #[default]
    Sound,
    /// Background music: ducked under the voice, faded in and out.
    Music,
}

/// An audio file placed on the timeline.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct AudioClip {
    pub path: String,
    /// Start time in seconds on the video timeline.
    pub start: f64,
    /// Linear gain (1.0 = unchanged).
    pub gain: f64,
    pub role: ClipRole,
    /// Music only: level under the voice (0.25 = a quarter); 0 = no ducking.
    pub duck: f64,
    /// Music only: fade in at its start and out at the end, in seconds.
    pub fade: f64,
    /// Music only: where it stops on the video timeline (the end of its scene in a movie);
    /// `None` = the end of the output.
    pub end: Option<f64>,
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
    /// Integrated loudness target of the audio track in LUFS; `None` keeps the mixed level.
    pub loudness: Option<f64>,
}

impl EncoderOptions {
    pub fn frame_len(&self) -> usize {
        self.width as usize * self.height as usize * 4
    }
}
