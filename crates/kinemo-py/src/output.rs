//! Outputs: frames (PNG/RGBA) and video files.

use std::path::PathBuf;

use pyo3::prelude::*;
use pyo3::types::PyBytes;

use kinemo_encode::Format;
use kinemo_render::{raster, render_frame, render_movie as render_movie_frames, render_video, render_video_range, Quality, RenderOptions, Transition};

use crate::builder::Builder;
use crate::errors::runtime;

fn quality(name: &str) -> PyResult<Quality> {
    match name {
        "draft" => Ok(Quality::Draft),
        "final" => Ok(Quality::Final),
        other => Err(pyo3::exceptions::PyValueError::new_err(format!("unknown quality '{other}'"))),
    }
}

fn format(name: &str) -> PyResult<Format> {
    match name {
        "mp4" => Ok(Format::Mp4),
        "webm" => Ok(Format::Webm),
        "mov" => Ok(Format::Mov),
        "gif" => Ok(Format::Gif),
        other => Err(pyo3::exceptions::PyValueError::new_err(format!("unknown video format '{other}'"))),
    }
}

impl Builder {
    pub(crate) fn options(&self, quality_name: &str, transparent: bool) -> PyResult<RenderOptions> {
        let mut o = RenderOptions::for_scene(&self.scene, quality(quality_name)?);
        o.transparent = transparent;
        Ok(o)
    }
}

#[pymethods]
impl Builder {
    /// PNG bytes of a contact sheet: the frames at `times`, labelled, in `columns` columns.
    #[pyo3(signature = (times, labels, columns = 3))]
    fn contact_sheet_png<'py>(&self, py: Python<'py>, times: Vec<f64>, labels: Vec<String>, columns: usize) -> PyResult<Bound<'py, PyBytes>> {
        let scene = &self.scene;
        let frames: Vec<(f64, String)> = times.into_iter().zip(labels).collect();
        let png = py.detach(|| raster::encode_png(&kinemo_render::sheet::contact_sheet(scene, &frames, columns)));
        Ok(PyBytes::new(py, &png))
    }

    /// PNG bytes of the frame at `t`.
    #[pyo3(signature = (t, quality = "final", transparent = false))]
    fn frame_png<'py>(&self, py: Python<'py>, t: f64, quality: &str, transparent: bool) -> PyResult<Bound<'py, PyBytes>> {
        let opts = self.options(quality, transparent)?;
        let scene = &self.scene;
        let png = py.detach(|| raster::encode_png(&render_frame(scene, t, &opts)));
        Ok(PyBytes::new(py, &png))
    }

    /// Writes `count` frames at `i / fps` as `folder/00000.png`, ... rendered, encoded and
    /// written in parallel. `progress(done, total)` is called from Python.
    #[pyo3(signature = (folder, count, fps, quality = "final", transparent = false, progress = None))]
    #[allow(clippy::too_many_arguments)] // the Python signature: keyword arguments with defaults
    fn render_frames(&self, py: Python<'_>, folder: PathBuf, count: usize, fps: f64, quality: &str, transparent: bool, progress: Option<Py<PyAny>>) -> PyResult<()> {
        let opts = self.options(quality, transparent)?;
        let scene = &self.scene;
        let report = move |done: usize, total: usize| {
            if let Some(cb) = &progress {
                Python::attach(|py| {
                    let _ = cb.call1(py, (done, total));
                });
            }
        };
        py.detach(|| kinemo_render::render_png_frames(scene, &folder, count, fps, &opts, &report)).map_err(runtime)
    }

    /// SVG document of the frame at `t` (vector, scene resolution).
    #[pyo3(signature = (t, transparent = false))]
    fn frame_svg(&self, t: f64, transparent: bool) -> String {
        kinemo_render::render_svg(&self.scene, t, transparent)
    }

    /// Raw straight-alpha RGBA8 frame at `t`: (width, height, bytes).
    #[pyo3(signature = (t, quality = "draft"))]
    fn frame_rgba<'py>(&self, py: Python<'py>, t: f64, quality: &str) -> PyResult<(u32, u32, Bound<'py, PyBytes>)> {
        let opts = self.options(quality, false)?;
        let scene = &self.scene;
        let img = py.detach(|| render_frame(scene, t, &opts));
        Ok((img.width, img.height, PyBytes::new(py, &img.rgba)))
    }

    /// Renders the scene to a video file. `progress(done, total)` is called from Python.
    #[pyo3(signature = (path, format = "mp4", quality = "final", transparent = false, progress = None))]
    fn render_video(
        &self,
        py: Python<'_>,
        path: PathBuf,
        format: &str,
        quality: &str,
        transparent: bool,
        progress: Option<Py<PyAny>>,
    ) -> PyResult<()> {
        let opts = self.options(quality, transparent)?;
        let fmt = self::format(format)?;
        let scene = &self.scene;
        let report = move |done: usize, total: usize| {
            if let Some(cb) = &progress {
                Python::attach(|py| {
                    let _ = cb.call1(py, (done, total));
                });
            }
        };
        py.detach(|| render_video(scene, &path, fmt, &opts, &report)).map_err(runtime)
    }

    /// Renders `[start, end)` to a video file (one slide section).
    #[pyo3(signature = (path, start, end, format = "mp4", quality = "final"))]
    fn render_section(&self, py: Python<'_>, path: PathBuf, start: f64, end: f64, format: &str, quality: &str) -> PyResult<()> {
        let opts = self.options(quality, false)?;
        let fmt = self::format(format)?;
        let scene = &self.scene;
        py.detach(|| render_video_range(scene, &path, fmt, &opts, (start, end), &|_, _| {})).map_err(runtime)
    }
}

#[pyfunction]
pub fn ffmpeg_available() -> bool {
    kinemo_encode::ffmpeg_available()
}

/// Where kinemo finds ffmpeg (`KINEMO_FFMPEG`, then `PATH`, then common locations); the
/// reason when it does not.
#[pyfunction]
pub fn ffmpeg_location() -> PyResult<String> {
    kinemo_encode::find_ffmpeg().map(|path| path.display().to_string()).map_err(runtime)
}

/// Logical box (x0, y0, x1, y1) of a text layout, for tests and tooling.
#[pyfunction]
#[pyo3(signature = (text, size = 0.5))]
pub fn measure_text(text: &str, size: f64) -> (f64, f64, f64, f64) {
    let r = kinemo_text::measure(text, &kinemo_text::TextOptions { size, ..Default::default() });
    (r.x0, r.y0, r.x1, r.y1)
}

/// Renders several built scenes into one video. `transitions[i]` joins scene i and i+1:
/// ("cut", 0) or ("crossfade", seconds). Quality and size come from the first scene.
#[pyfunction]
#[pyo3(signature = (builders, transitions, path, format = "mp4", quality = "final", progress = None))]
pub fn render_movie(
    py: Python<'_>,
    builders: Vec<PyRef<'_, Builder>>,
    transitions: Vec<(String, f64)>,
    path: PathBuf,
    format: &str,
    quality: &str,
    progress: Option<Py<PyAny>>,
) -> PyResult<()> {
    let Some(first) = builders.first() else { return Ok(()) };
    let opts = first.options(quality, false)?;
    let fmt = self::format(format)?;
    let scenes: Vec<kinemo_ir::Scene> = builders.iter().map(|b| b.scene.clone()).collect();
    let refs: Vec<&kinemo_ir::Scene> = scenes.iter().collect();
    let transitions: Vec<Transition> = transitions
        .iter()
        .map(|(kind, d)| if kind == "crossfade" { Transition::Crossfade(*d) } else { Transition::Cut })
        .collect();
    let report = move |done: usize, total: usize| {
        if let Some(cb) = &progress {
            Python::attach(|py| {
                let _ = cb.call1(py, (done, total));
            });
        }
    };
    py.detach(|| render_movie_frames(&refs, &transitions, &path, fmt, &opts, &report)).map_err(runtime)
}
