//! Frame and video rendering with quality presets and parallel rasterization.

use std::path::Path;
use std::sync::Arc;

use rayon::prelude::*;

use kinemo_encode::{AudioClip, ClipRole, EncodeError, EncoderOptions, Format, VideoEncoder};
use kinemo_eval::{Evaluator, TimelineIndex};
use kinemo_layout::Layout;
use kinemo_ir::Scene;

use crate::frame::{display_list, display_list_indexed, display_list_with, FrameSize};
use crate::raster::{rasterize, Image, RenderBackend};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Quality {
    /// 540p, 30 fps: the `dev` default.
    Draft,
    /// The scene's own resolution and fps.
    Final,
}

#[derive(Clone, Debug, PartialEq)]
pub struct RenderOptions {
    pub width: u32,
    pub height: u32,
    pub fps: f64,
    pub antialias: bool,
    pub transparent: bool,
}

impl RenderOptions {
    pub fn for_scene(scene: &Scene, quality: Quality) -> Self {
        let c = &scene.config;
        match quality {
            Quality::Final => RenderOptions { width: c.width, height: c.height, fps: c.fps, antialias: true, transparent: false },
            Quality::Draft => {
                let k = (540.0 / c.height.min(c.width) as f64).min(1.0);
                RenderOptions {
                    width: even((c.width as f64 * k).round() as u32),
                    height: even((c.height as f64 * k).round() as u32),
                    fps: c.fps.min(30.0),
                    antialias: true,
                    transparent: false,
                }
            }
        }
    }

    fn size(&self) -> FrameSize {
        FrameSize { width: self.width, height: self.height }
    }

    pub fn frame_count(&self, duration: f64) -> usize {
        ((duration * self.fps).ceil() as usize).max(1)
    }
}

fn even(v: u32) -> u32 {
    v + (v & 1)
}

pub fn render_frame(scene: &Scene, t: f64, opts: &RenderOptions) -> Image {
    rasterize(&display_list(scene, t, opts.size(), opts.transparent), opts.antialias)
}

/// [`render_frame`] sharing `index` (made for `scene`) with the other frames of a render.
pub fn render_frame_indexed(scene: &Scene, index: &Arc<TimelineIndex>, t: f64, opts: &RenderOptions) -> Image {
    rasterize(&display_list_indexed(scene, index, t, opts.size(), opts.transparent), opts.antialias)
}

/// [`render_frame`] through an explicit rasterization backend (e.g. the GPU in preview).
pub fn render_frame_with_backend(backend: &dyn RenderBackend, scene: &Scene, t: f64, opts: &RenderOptions) -> Image {
    backend.rasterize(&display_list(scene, t, opts.size(), opts.transparent), opts.antialias)
}

/// The encoder's view of an audio clip of the scene, starting at `start` in the output.
/// `end`: where the clip's scene ends on the output timeline (music stops there), `None` for a
/// single scene.
pub(crate) fn audio_clip(audio: &kinemo_ir::Audio, start: f64, end: Option<f64>) -> AudioClip {
    let role = match audio.role {
        kinemo_ir::AudioRole::Voice => ClipRole::Voice,
        kinemo_ir::AudioRole::Sound => ClipRole::Sound,
        kinemo_ir::AudioRole::Music => ClipRole::Music,
    };
    AudioClip { path: audio.path.clone(), start, gain: audio.gain, role, duck: audio.duck, fade: audio.fade, end }
}

#[derive(Debug)]
pub enum RenderError {
    Encode(EncodeError),
}

impl std::fmt::Display for RenderError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            RenderError::Encode(e) => write!(f, "{e}"),
        }
    }
}

impl std::error::Error for RenderError {}

impl From<EncodeError> for RenderError {
    fn from(e: EncodeError) -> Self {
        RenderError::Encode(e)
    }
}

/// Renders `count` frames at `0, 1/fps, 2/fps, ...` as numbered PNG files (`00000.png`, ...)
/// in `folder`, in parallel: rendering, PNG encoding and writing all run on every core.
/// `progress(done, total)` is called as files are written (from any thread).
pub fn render_png_frames(
    scene: &Scene,
    folder: &Path,
    count: usize,
    fps: f64,
    opts: &RenderOptions,
    progress: &(dyn Fn(usize, usize) + Sync),
) -> std::io::Result<()> {
    std::fs::create_dir_all(folder)?;
    let index = Arc::new(TimelineIndex::new(scene));
    let done = std::sync::atomic::AtomicUsize::new(0);
    (0..count).into_par_iter().try_for_each_init(
        || Evaluator::with_index(scene, index.clone()),
        |evaluator, i| {
            evaluator.clear();
            let layout = Layout::new(evaluator);
            let list = display_list_with(&layout, i as f64 / fps, opts.size(), opts.transparent);
            let png = crate::raster::encode_png(&rasterize(&list, opts.antialias));
            std::fs::write(folder.join(format!("{i:05}.png")), png)?;
            progress(done.fetch_add(1, std::sync::atomic::Ordering::Relaxed) + 1, count);
            Ok(())
        },
    )
}

/// Renders the whole scene to a video file. `progress(done, total)` is called per frame.
pub fn render_video(
    scene: &Scene,
    path: &Path,
    format: Format,
    opts: &RenderOptions,
    progress: &(dyn Fn(usize, usize) + Sync),
) -> Result<(), RenderError> {
    render_video_range(scene, path, format, opts, (0.0, scene.duration), progress)
}

/// Renders the interval `[start, end)` of the scene (slides render one file per section).
pub fn render_video_range(
    scene: &Scene,
    path: &Path,
    format: Format,
    opts: &RenderOptions,
    (start_time, end_time): (f64, f64),
    progress: &(dyn Fn(usize, usize) + Sync),
) -> Result<(), RenderError> {
    let total = opts.frame_count((end_time - start_time).max(0.0));
    let audio = scene
        .audio
        .iter()
        .filter(|a| a.t >= start_time && a.t < end_time)
        .map(|a| audio_clip(a, a.t - start_time, None))
        .collect();
    let enc_opts = EncoderOptions {
        width: opts.width,
        height: opts.height,
        fps: opts.fps,
        format,
        transparent: opts.transparent,
        crf: None,
        audio,
        duration: total as f64 / opts.fps,
        loudness: scene.config.loudness,
    };
    let mut encoder = VideoEncoder::start(path, &enc_opts)?;
    let index = Arc::new(TimelineIndex::new(scene));
    const BATCH: usize = 32;
    let mut done = 0;
    for start in (0..total).step_by(BATCH) {
        let end = (start + BATCH).min(total);
        let frames: Vec<Image> = (start..end)
            .into_par_iter()
            .map_init(
                || Evaluator::with_index(scene, index.clone()),
                |evaluator, i| {
                    // One evaluator per worker: its caches keep their capacity between frames.
                    evaluator.clear();
                    let layout = Layout::new(evaluator);
                    let list = display_list_with(&layout, start_time + i as f64 / opts.fps, opts.size(), opts.transparent);
                    rasterize(&list, opts.antialias)
                },
            )
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
