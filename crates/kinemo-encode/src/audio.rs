//! Audio mixing filter graph: voices, sounds and music are mixed in groups so music can duck
//! under the voice (sidechain compression); the result is optionally normalized to a loudness
//! target, then limited so overlapping clips never clip.

use crate::{AudioClip, ClipRole};

/// Peak level of the limiter at the end of the chain (linear, below full scale).
const LIMIT: f64 = 0.95;

/// Build the `-filter_complex` fragment mixing `clips`, whose ffmpeg input
/// indices start at `first_input`. Output label is `[aout]`.
/// Returns `None` when there are no clips.
pub(crate) fn mix_graph(clips: &[AudioClip], first_input: usize, duration: f64, loudness: Option<f64>) -> Option<String> {
    if clips.is_empty() {
        return None;
    }
    let duration = duration.max(0.0);
    let mut parts = Vec::new();
    let (mut voices, mut sounds, mut music) = (String::new(), String::new(), String::new());
    for (i, clip) in clips.iter().enumerate() {
        let delay_ms = (clip.start.max(0.0) * 1000.0).round() as u64;
        let gain = if clip.gain.is_finite() { clip.gain.max(0.0) } else { 1.0 };
        let mut chain = format!("[{}:a]aresample=48000,aformat=channel_layouts=stereo", first_input + i);
        if clip.role == ClipRole::Music {
            // Clip-local times, before the delay: music plays until the end of its scene.
            let length = (clip.end.unwrap_or(duration).min(duration) - clip.start.max(0.0)).max(0.0);
            if clip.fade > 0.0 {
                let out_at = (length - clip.fade).max(0.0);
                chain.push_str(&format!(",afade=t=in:d={:.3},afade=t=out:st={out_at:.3}:d={:.3}", clip.fade, clip.fade));
            }
            if clip.end.is_some() {
                chain.push_str(&format!(",atrim=end={length:.3}"));
            }
        }
        chain.push_str(&format!(",adelay={delay_ms}:all=1,volume={gain:.6}[a{i}]"));
        parts.push(chain);
        let label = format!("[a{i}]");
        match clip.role {
            ClipRole::Voice => voices.push_str(&label),
            ClipRole::Sound => sounds.push_str(&label),
            ClipRole::Music => music.push_str(&label),
        }
    }
    let mix = |labels: &str, out: &str| -> String {
        let n = labels.matches('[').count();
        if n == 1 {
            format!("{labels}anull{out}")
        } else {
            format!("{labels}amix=inputs={n}:normalize=0:duration=longest:dropout_transition=0{out}")
        }
    };
    let mut groups = String::new();
    let duck = clips.iter().filter(|c| c.role == ClipRole::Music).map(|c| c.duck).fold(0.0_f64, f64::max);
    if !voices.is_empty() {
        if !music.is_empty() && duck > 0.0 {
            parts.push(mix(&voices, "[voices]"));
            parts.push("[voices]asplit=2[voice][sidechain]".into());
            parts.push(mix(&music, "[music]"));
            // The ratio brings the music down to about `duck` of its level while the voice speaks.
            let ratio = (1.0 / duck.clamp(0.05, 1.0)).clamp(1.0, 20.0);
            parts.push(format!("[music][sidechain]sidechaincompress=threshold=0.02:ratio={ratio:.3}:attack=20:release=300[ducked]"));
            groups.push_str("[voice][ducked]");
            music.clear();
        } else {
            parts.push(mix(&voices, "[voice]"));
            groups.push_str("[voice]");
        }
    }
    if !music.is_empty() {
        parts.push(mix(&music, "[music]"));
        groups.push_str("[music]");
    }
    if !sounds.is_empty() {
        parts.push(mix(&sounds, "[sounds]"));
        groups.push_str("[sounds]");
    }
    let mut tail = mix(&groups, "[mixed]");
    tail.push_str(";[mixed]");
    if let Some(target) = loudness {
        tail.push_str(&format!("loudnorm=I={target:.1}:TP=-1.5:LRA=11,aresample=48000,"));
    }
    tail.push_str(&format!("alimiter=limit={LIMIT}:level=disabled,atrim=0:{duration:.6},apad=whole_dur={duration:.6}[aout]"));
    parts.push(tail);
    Some(parts.join(";"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn music_with_an_end_fades_and_stops_there() {
        let bed = AudioClip { path: "bed.wav".into(), start: 1.0, gain: 0.3, role: ClipRole::Music, duck: 0.0, fade: 0.5, end: Some(4.0) };
        let g = mix_graph(&[bed], 1, 10.0, None).unwrap();
        assert!(g.contains("afade=t=out:st=2.500:d=0.500"), "{g}");
        assert!(g.contains("atrim=end=3.000"), "{g}");
    }

    fn clip(path: &str, start: f64, role: ClipRole) -> AudioClip {
        AudioClip { path: path.into(), start, gain: 1.0, role, ..AudioClip::default() }
    }

    #[test]
    fn graph_shape() {
        let clips = vec![
            AudioClip { path: "a.wav".into(), start: 0.5, gain: 0.8, ..AudioClip::default() },
            AudioClip { path: "b.wav".into(), start: 0.0, gain: 1.0, ..AudioClip::default() },
        ];
        let g = mix_graph(&clips, 1, 2.0, None).unwrap();
        assert!(g.contains("[1:a]") && g.contains("[2:a]"));
        assert!(g.contains("adelay=500:all=1"));
        assert!(g.contains("amix=inputs=2:normalize=0"));
        assert!(g.contains("alimiter") && !g.contains("loudnorm"));
        assert!(g.ends_with("[aout]"));
        assert!(mix_graph(&[], 1, 2.0, None).is_none());
    }

    #[test]
    fn music_ducks_under_the_voice_and_fades() {
        let clips = vec![
            clip("voice.wav", 1.0, ClipRole::Voice),
            AudioClip { path: "bed.mp3".into(), start: 0.0, gain: 0.3, role: ClipRole::Music, duck: 0.25, fade: 1.0, end: None },
        ];
        let g = mix_graph(&clips, 1, 10.0, Some(-16.0)).unwrap();
        assert!(g.contains("asplit=2[voice][sidechain]"));
        assert!(g.contains("[music][sidechain]sidechaincompress=") && g.contains("ratio=4.000"));
        assert!(g.contains("afade=t=in:d=1.000,afade=t=out:st=9.000:d=1.000"));
        assert!(g.contains("loudnorm=I=-16.0"));
    }

    #[test]
    fn music_without_a_voice_is_mixed_as_is() {
        let g = mix_graph(&[clip("bed.mp3", 0.0, ClipRole::Music)], 1, 4.0, None).unwrap();
        assert!(!g.contains("sidechaincompress") && g.contains("[music]"));
    }
}
