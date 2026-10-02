use std::fmt;

#[derive(Debug)]
pub enum EncodeError {
    /// The ffmpeg binary could not be located.
    NotFound(String),
    Io(std::io::Error),
    /// ffmpeg failed or the input was invalid; carries a message / ffmpeg's stderr.
    Ffmpeg(String),
}

impl fmt::Display for EncodeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EncodeError::NotFound(m) => write!(f, "ffmpeg not found: {m}"),
            EncodeError::Io(e) => write!(f, "I/O error while encoding: {e}"),
            EncodeError::Ffmpeg(m) => write!(f, "ffmpeg failed: {m}"),
        }
    }
}

impl std::error::Error for EncodeError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            EncodeError::Io(e) => Some(e),
            _ => None,
        }
    }
}

impl From<std::io::Error> for EncodeError {
    fn from(e: std::io::Error) -> Self {
        EncodeError::Io(e)
    }
}
