//! Locating the ffmpeg binary.

use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use crate::EncodeError;

const FALLBACK_LOCATIONS: &[&str] = &["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"];

fn is_executable(p: &Path) -> bool {
    p.is_file()
}

/// Locate ffmpeg: `KINEMO_FFMPEG` env var, then `PATH`, then common locations.
pub fn find_ffmpeg() -> Result<PathBuf, EncodeError> {
    if let Some(v) = std::env::var_os("KINEMO_FFMPEG") {
        let p = PathBuf::from(&v);
        return if is_executable(&p) {
            Ok(p)
        } else {
            Err(EncodeError::NotFound(format!("KINEMO_FFMPEG={} is not a file", p.display())))
        };
    }
    let exe = if cfg!(windows) { "ffmpeg.exe" } else { "ffmpeg" };
    if let Some(path) = std::env::var_os("PATH") {
        for dir in std::env::split_paths(&path) {
            let cand = dir.join(exe);
            if is_executable(&cand) {
                return Ok(cand);
            }
        }
    }
    for loc in FALLBACK_LOCATIONS {
        let p = PathBuf::from(loc);
        if is_executable(&p) {
            return Ok(p);
        }
    }
    Err(EncodeError::NotFound(
        "install ffmpeg or set KINEMO_FFMPEG to its path".to_string(),
    ))
}

/// True when an ffmpeg binary is found and `ffmpeg -version` runs successfully.
pub fn ffmpeg_available() -> bool {
    let Ok(p) = find_ffmpeg() else { return false };
    Command::new(p)
        .arg("-version")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}
