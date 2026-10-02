//! Audio mixing filter graph.

use crate::AudioClip;

/// Build the `-filter_complex` fragment mixing `clips`, whose ffmpeg input
/// indices start at `first_input`. Output label is `[aout]`.
/// Returns `None` when there are no clips.
pub(crate) fn mix_graph(clips: &[AudioClip], first_input: usize, duration: f64) -> Option<String> {
    if clips.is_empty() {
        return None;
    }
    let mut parts = Vec::with_capacity(clips.len() + 1);
    let mut labels = String::new();
    for (i, clip) in clips.iter().enumerate() {
        let delay_ms = (clip.start.max(0.0) * 1000.0).round() as u64;
        let gain = if clip.gain.is_finite() { clip.gain.max(0.0) } else { 1.0 };
        parts.push(format!(
            "[{}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={delay_ms}:all=1,volume={gain:.6}[a{i}]",
            first_input + i
        ));
        labels.push_str(&format!("[a{i}]"));
    }
    parts.push(format!(
        "{labels}amix=inputs={}:normalize=0:duration=longest:dropout_transition=0,atrim=0:{:.6},apad=whole_dur={:.6}[aout]",
        clips.len(),
        duration.max(0.0),
        duration.max(0.0),
    ));
    Some(parts.join(";"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn graph_shape() {
        let clips = vec![
            AudioClip { path: "a.wav".into(), start: 0.5, gain: 0.8 },
            AudioClip { path: "b.wav".into(), start: 0.0, gain: 1.0 },
        ];
        let g = mix_graph(&clips, 1, 2.0).unwrap();
        assert!(g.contains("[1:a]") && g.contains("[2:a]"));
        assert!(g.contains("adelay=500:all=1"));
        assert!(g.contains("amix=inputs=2:normalize=0"));
        assert!(g.ends_with("[aout]"));
        assert!(mix_graph(&[], 1, 2.0).is_none());
    }
}
