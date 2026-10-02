//! The ffmpeg subprocess lifecycle.

use std::io::{Read, Write};
use std::path::Path;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::thread::JoinHandle;

use crate::{audio, formats, EncodeError, EncoderOptions, Format};

/// Streams raw RGBA frames into an ffmpeg process.
pub struct VideoEncoder {
    child: Option<Child>,
    stdin: Option<ChildStdin>,
    stderr: Option<JoinHandle<String>>,
    frame_len: usize,
    frames: u64,
}

fn validate(opts: &EncoderOptions) -> Result<(), EncodeError> {
    let bad = |m: &str| Err(EncodeError::Ffmpeg(format!("invalid options: {m}")));
    if opts.width == 0 || opts.height == 0 {
        return bad("width and height must be > 0");
    }
    if !(opts.fps.is_finite() && opts.fps > 0.0) {
        return bad("fps must be > 0");
    }
    Ok(())
}

/// Full ffmpeg argument list (everything after the binary name).
pub(crate) fn build_args(path: &Path, opts: &EncoderOptions) -> Vec<String> {
    let mut a: Vec<String> = ["-hide_banner", "-loglevel", "error", "-nostats", "-y"]
        .iter()
        .map(|s| s.to_string())
        .collect();
    let push = |a: &mut Vec<String>, xs: &[&str]| a.extend(xs.iter().map(|s| s.to_string()));
    push(&mut a, &["-f", "rawvideo", "-pix_fmt", "rgba"]);
    push(&mut a, &["-s", &format!("{}x{}", opts.width, opts.height)]);
    push(&mut a, &["-framerate", &formats::fps_rational(opts.fps), "-i", "pipe:0"]);

    let audio_args = formats::audio_codec_args(opts.format);
    let clips = if audio_args.is_some() { &opts.audio[..] } else { &[][..] };
    for clip in clips {
        push(&mut a, &["-i", &clip.path]);
    }

    let mut graph = formats::video_graph(opts);
    let audio_graph = audio::mix_graph(clips, 1, opts.duration);
    if let Some(ag) = &audio_graph {
        graph.push(';');
        graph.push_str(ag);
    }
    push(&mut a, &["-filter_complex_threads", "1", "-filter_complex", &graph]);
    push(&mut a, &["-map", formats::VIDEO_OUT]);
    a.extend(formats::video_codec_args(opts));
    if audio_graph.is_some() {
        push(&mut a, &["-map", "[aout]"]);
        a.extend(audio_args.unwrap());
        push(&mut a, &["-flags:a", "+bitexact"]);
    }
    push(&mut a, &["-flags:v", "+bitexact", "-fflags", "+bitexact"]);
    push(&mut a, &["-map_metadata", "-1", "-map_chapters", "-1"]);
    push(&mut a, &["-f", formats::muxer(opts.format)]);
    a.push(path.to_string_lossy().into_owned());
    a
}

impl VideoEncoder {
    /// Spawn ffmpeg writing `path`, reading rawvideo RGBA from stdin.
    pub fn start(path: &Path, opts: &EncoderOptions) -> Result<Self, EncodeError> {
        validate(opts)?;
        for clip in &opts.audio {
            if opts.format != Format::Gif && !Path::new(&clip.path).is_file() {
                return Err(EncodeError::Ffmpeg(format!("audio file not found: {}", clip.path)));
            }
        }
        let bin = crate::find_ffmpeg()?;
        let mut child = Command::new(&bin)
            .args(build_args(path, opts))
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| match e.kind() {
                std::io::ErrorKind::NotFound => EncodeError::NotFound(bin.display().to_string()),
                _ => EncodeError::Io(e),
            })?;
        let stdin = child.stdin.take();
        // Drain stderr on a thread so ffmpeg can never block on a full pipe.
        let stderr = child.stderr.take().map(|mut err| {
            std::thread::spawn(move || {
                let mut buf = String::new();
                let _ = err.read_to_string(&mut buf);
                buf
            })
        });
        Ok(VideoEncoder { child: Some(child), stdin, stderr, frame_len: opts.frame_len(), frames: 0 })
    }

    /// Number of frames pushed so far.
    pub fn frames(&self) -> u64 {
        self.frames
    }

    /// Write one straight-alpha RGBA8 frame of exactly `width * height * 4` bytes.
    pub fn push_frame(&mut self, rgba: &[u8]) -> Result<(), EncodeError> {
        if rgba.len() != self.frame_len {
            return Err(EncodeError::Ffmpeg(format!(
                "frame has {} bytes, expected {}",
                rgba.len(),
                self.frame_len
            )));
        }
        let stdin = self.stdin.as_mut().expect("encoder already finished");
        match stdin.write_all(rgba) {
            Ok(()) => {
                self.frames += 1;
                Ok(())
            }
            // ffmpeg exited early: report its stderr rather than a bare broken pipe.
            Err(e) if e.kind() == std::io::ErrorKind::BrokenPipe => {
                self.shutdown()?;
                Err(EncodeError::Ffmpeg("ffmpeg exited before all frames were written".into()))
            }
            Err(e) => Err(EncodeError::Io(e)),
        }
    }

    /// Close stdin and wait for ffmpeg; on failure, the error carries ffmpeg's stderr.
    pub fn finish(mut self) -> Result<(), EncodeError> {
        self.shutdown()
    }

    fn shutdown(&mut self) -> Result<(), EncodeError> {
        drop(self.stdin.take());
        let Some(mut child) = self.child.take() else { return Ok(()) };
        let status = child.wait()?;
        let err = self.stderr.take().and_then(|h| h.join().ok()).unwrap_or_default();
        if status.success() {
            Ok(())
        } else {
            Err(EncodeError::Ffmpeg(format!("exit status {status}: {}", err.trim())))
        }
    }
}

impl Drop for VideoEncoder {
    /// Dropping without `finish` aborts the encode.
    fn drop(&mut self) {
        drop(self.stdin.take());
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}
