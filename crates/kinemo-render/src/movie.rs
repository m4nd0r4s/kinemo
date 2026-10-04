//! Movies: several scenes in one output, joined by cuts or crossfades.

use std::path::Path;

use rayon::prelude::*;

use kinemo_encode::{EncoderOptions, Format, VideoEncoder};
use kinemo_ir::Scene;

use crate::raster::Image;
use crate::renderer::{render_frame, RenderError, RenderOptions};

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Transition {
    Cut,
    /// The end of one scene and the start of the next overlap for this many seconds.
    Crossfade(f64),
}

impl Transition {
    fn overlap(&self) -> f64 {
        match self {
            Transition::Cut => 0.0,
            Transition::Crossfade(d) => d.max(0.0),
        }
    }
}

/// Where each scene starts on the movie timeline.
pub fn scene_starts(scenes: &[&Scene], transitions: &[Transition]) -> Vec<f64> {
    let mut starts = Vec::with_capacity(scenes.len());
    let mut t = 0.0;
    for (i, s) in scenes.iter().enumerate() {
        starts.push(t);
        let overlap = transitions.get(i).map_or(0.0, |tr| tr.overlap()).min(s.duration);
        t += s.duration - overlap;
    }
    starts
}

fn blend(a: &Image, b: &Image, alpha: f64) -> Image {
    let rgba = a
        .rgba
        .iter()
        .zip(&b.rgba)
        .map(|(&x, &y)| (x as f64 + (y as f64 - x as f64) * alpha).round() as u8)
        .collect();
    Image { width: a.width, height: a.height, rgba }
}

/// Frame of the movie at time `t`.
fn movie_frame(scenes: &[&Scene], starts: &[f64], t: f64, opts: &RenderOptions) -> Image {
    let active: Vec<usize> = (0..scenes.len())
        .filter(|&i| t >= starts[i] - 1e-9 && t < starts[i] + scenes[i].duration)
        .collect();
    match active.as_slice() {
        [] => render_frame(scenes[scenes.len() - 1], scenes[scenes.len() - 1].duration, opts),
        [i] => render_frame(scenes[*i], t - starts[*i], opts),
        [i, j, ..] => {
            let overlap_start = starts[*j];
            let overlap_end = starts[*i] + scenes[*i].duration;
            let alpha = ((t - overlap_start) / (overlap_end - overlap_start).max(1e-9)).clamp(0.0, 1.0);
            let a = render_frame(scenes[*i], t - starts[*i], opts);
            let b = render_frame(scenes[*j], t - starts[*j], opts);
            blend(&a, &b, alpha)
        }
    }
}

pub fn render_movie(
    scenes: &[&Scene],
    transitions: &[Transition],
    path: &Path,
    format: Format,
    opts: &RenderOptions,
    progress: &(dyn Fn(usize, usize) + Sync),
) -> Result<(), RenderError> {
    if scenes.is_empty() {
        return Ok(());
    }
    let starts = scene_starts(scenes, transitions);
    let last = scenes.len() - 1;
    let duration = starts[last] + scenes[last].duration;
    let total = opts.frame_count(duration);
    let audio = scenes
        .iter()
        .zip(&starts)
        .flat_map(|(s, start)| s.audio.iter().map(move |a| crate::renderer::audio_clip(a, start + a.t)))
        .collect();
    let enc = EncoderOptions {
        width: opts.width,
        height: opts.height,
        fps: opts.fps,
        format,
        transparent: opts.transparent,
        crf: None,
        audio,
        duration: total as f64 / opts.fps,
        // A movie takes the loudness of its first scene.
        loudness: scenes[0].config.loudness,
    };
    let mut encoder = VideoEncoder::start(path, &enc)?;
    const BATCH: usize = 32;
    let mut done = 0;
    for first in (0..total).step_by(BATCH) {
        let frames: Vec<Image> = (first..(first + BATCH).min(total))
            .into_par_iter()
            .map(|i| movie_frame(scenes, &starts, i as f64 / opts.fps, opts))
            .collect();
        for f in frames {
            encoder.push_frame(&f.rgba)?;
            done += 1;
            progress(done, total);
        }
    }
    encoder.finish()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use kinemo_ir::SceneConfig;

    fn scene(duration: f64) -> Scene {
        let mut s = Scene::new(SceneConfig::default());
        s.duration = duration;
        s
    }

    #[test]
    fn crossfade_overlaps_scenes() {
        let (a, b, c) = (scene(3.0), scene(2.0), scene(1.0));
        let starts = scene_starts(&[&a, &b, &c], &[Transition::Crossfade(0.5), Transition::Cut]);
        assert_eq!(starts, vec![0.0, 2.5, 4.5]);
    }

    #[test]
    fn blend_is_linear() {
        let a = Image { width: 1, height: 1, rgba: vec![0, 0, 0, 255] };
        let b = Image { width: 1, height: 1, rgba: vec![200, 100, 50, 255] };
        assert_eq!(blend(&a, &b, 0.5).rgba, vec![100, 50, 25, 255]);
    }
}
