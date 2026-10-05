use std::path::{Path, PathBuf};
use std::process::Command;

use kinemo_encode::*;

const W: u32 = 64;
const H: u32 = 64;
const N: usize = 10;

fn tmp(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join(format!("kinemo-encode-test-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    dir.join(name)
}

fn frame(i: usize) -> Vec<u8> {
    let mut v = Vec::with_capacity((W * H * 4) as usize);
    for y in 0..H {
        for x in 0..W {
            let inside = (x as usize) >= i * 4 && (x as usize) < i * 4 + 16 && (24..40).contains(&y);
            if inside {
                v.extend_from_slice(&[255, 0, 0, 255]);
            } else {
                v.extend_from_slice(&[(x * 2) as u8, (y * 3) as u8, 40, 128]);
            }
        }
    }
    v
}

fn opts(format: Format) -> EncoderOptions {
    EncoderOptions {
        width: W,
        height: H,
        fps: 10.0,
        format,
        transparent: false,
        crf: None,
        audio: vec![],
        duration: N as f64 / 10.0,
        loudness: None,
    }
}

fn encode(path: &Path, o: &EncoderOptions) {
    let mut enc = VideoEncoder::start(path, o).unwrap();
    for i in 0..N {
        enc.push_frame(&o.encoder_frame(frame(i))).unwrap();
    }
    enc.finish().unwrap();
}

fn count_frames(path: &Path) -> usize {
    let out = Command::new(find_ffmpeg().unwrap())
        .args(["-v", "error", "-i"])
        .arg(path)
        .args(["-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "rgba", "-"])
        .output()
        .unwrap();
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    out.stdout.len() / (W * H * 4) as usize
}

macro_rules! need_ffmpeg {
    () => {
        if !ffmpeg_available() {
            eprintln!("ffmpeg not available; skipping");
            return;
        }
    };
}

fn determinism(format: Format, transparent: bool, ext: &str) {
    let mut o = opts(format);
    o.transparent = transparent;
    let a = tmp(&format!("a_{transparent}.{ext}"));
    let b = tmp(&format!("b_{transparent}.{ext}"));
    encode(&a, &o);
    encode(&b, &o);
    let (ba, bb) = (std::fs::read(&a).unwrap(), std::fs::read(&b).unwrap());
    assert!(!ba.is_empty());
    assert!(ba == bb, "{format:?} output not byte-identical");
    assert_eq!(count_frames(&a), N);
}

#[test]
fn mp4_deterministic_roundtrip() {
    need_ffmpeg!();
    determinism(Format::Mp4, false, "mp4");
}

#[test]
fn webm_deterministic_alpha() {
    need_ffmpeg!();
    determinism(Format::Webm, true, "webm");
}

#[test]
fn mov_deterministic_alpha() {
    need_ffmpeg!();
    determinism(Format::Mov, true, "mov");
}

#[test]
fn gif_deterministic() {
    need_ffmpeg!();
    determinism(Format::Gif, false, "gif");
}

#[test]
fn mp4_with_audio() {
    need_ffmpeg!();
    let wav = tmp("tone.wav");
    let st = Command::new(find_ffmpeg().unwrap())
        .args(["-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=0.5", "-ac", "1"])
        .arg(&wav)
        .status()
        .unwrap();
    assert!(st.success());
    let mut o = opts(Format::Mp4);
    o.audio = vec![
        AudioClip { path: wav.to_string_lossy().into(), start: 0.2, gain: 0.5, ..AudioClip::default() },
        AudioClip { path: wav.to_string_lossy().into(), start: 0.0, gain: 1.0, ..AudioClip::default() },
    ];
    let a = tmp("audio_a.mp4");
    let b = tmp("audio_b.mp4");
    encode(&a, &o);
    encode(&b, &o);
    assert_eq!(std::fs::read(&a).unwrap(), std::fs::read(&b).unwrap());
    let out = Command::new(find_ffmpeg().unwrap()).arg("-i").arg(&a).output().unwrap();
    let info = String::from_utf8_lossy(&out.stderr);
    assert!(info.contains("Audio: aac"), "{info}");
}

#[test]
fn voice_over_ducked_music_normalized() {
    need_ffmpeg!();
    let tone = |name: &str, frequency: u32| {
        let path = tmp(name);
        let st = Command::new(find_ffmpeg().unwrap())
            .args(["-v", "error", "-y", "-f", "lavfi", "-i", &format!("sine=frequency={frequency}:duration=1"), "-ac", "1"])
            .arg(&path)
            .status()
            .unwrap();
        assert!(st.success());
        path.to_string_lossy().into_owned()
    };
    let mut o = opts(Format::Mp4);
    o.audio = vec![
        AudioClip { path: tone("voice.wav", 300), start: 0.2, gain: 1.0, role: ClipRole::Voice, ..AudioClip::default() },
        AudioClip { path: tone("bed.wav", 600), start: 0.0, gain: 0.5, role: ClipRole::Music, duck: 0.25, fade: 0.3, end: None },
    ];
    o.loudness = Some(-16.0);
    let out = tmp("ducked.mp4");
    encode(&out, &o);
    let probe = Command::new(find_ffmpeg().unwrap()).arg("-i").arg(&out).output().unwrap();
    assert!(String::from_utf8_lossy(&probe.stderr).contains("Audio: aac"));
}

#[test]
fn wrong_frame_size_is_error() {
    need_ffmpeg!();
    let mut enc = VideoEncoder::start(&tmp("bad.mp4"), &opts(Format::Mp4)).unwrap();
    assert!(matches!(enc.push_frame(&[0u8; 10]), Err(EncodeError::Ffmpeg(_))));
}

#[test]
fn ffmpeg_failure_surfaces_stderr() {
    need_ffmpeg!();
    let path = Path::new("/nonexistent-dir-kinemo/out.mp4");
    let o = opts(Format::Mp4);
    let r = VideoEncoder::start(path, &o).and_then(|mut e| {
        for i in 0..N {
            e.push_frame(&o.encoder_frame(frame(i)))?;
        }
        e.finish()
    });
    match r {
        Err(EncodeError::Ffmpeg(msg)) => assert!(!msg.is_empty()),
        other => panic!("expected ffmpeg error, got {other:?}"),
    }
}

#[test]
fn missing_binary_reports_not_found() {
    // Only checks the error type's Display; does not mutate the environment.
    let e = EncodeError::NotFound("x".into());
    assert!(e.to_string().contains("ffmpeg not found"));
}
