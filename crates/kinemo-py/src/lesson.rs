//! What a lesson export ships besides the IR: the formula layouts and code tokens its frames
//! use, which the WASM player cannot compute (it is built without typst and tree-sitter).

use pyo3::prelude::*;

use kinemo_render::{display_list_with, FrameSize};

use crate::builder::{layout_at, Builder};

#[pymethods]
impl Builder {
    /// `{"math": [...], "code": [...]}` for every frame at `i / fps`: lays each frame out once
    /// while recording what typst and tree-sitter compute.
    fn baked_layouts(&self, py: Python<'_>, fps: f64) -> String {
        let scene = &self.scene;
        py.detach(|| {
            kinemo_math::baked::start_recording();
            kinemo_code::baked::start_recording();
            let count = ((scene.duration * fps).ceil() as usize).max(1);
            let times: Vec<f64> = (0..=count).map(|i| (i as f64 / fps).min(scene.duration)).collect();
            let size = FrameSize { width: scene.config.width, height: scene.config.height };
            layout_at(scene, &times, |layout, t| {
                display_list_with(layout, t, size, false);
            });
            format!(r#"{{"math":{},"code":{}}}"#, kinemo_math::baked::recorded(), kinemo_code::baked::recorded())
        })
    }
}
