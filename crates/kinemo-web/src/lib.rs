//! The lesson player's core in WebAssembly: load a scene's IR once, then render any time `t`
//! into an RGBA buffer the page puts on a canvas.

use std::sync::Arc;

use kinemo_eval::TimelineIndex;
use kinemo_ir::Scene;
use kinemo_render::raster::{rasterize, DisplayList};
use kinemo_render::{display_list_indexed, FrameSize, RenderOptions};
use wasm_bindgen::prelude::*;

/// Register what the export computed natively (`{"math": [...], "code": [...]}`): formula
/// layouts and code tokens, which this build cannot make. Call before the first frame.
#[wasm_bindgen]
pub fn bake(json: &str) -> Result<(), JsError> {
    let baked: serde_json::Value = serde_json::from_str(json)?;
    if let Some(math) = baked.get("math") {
        kinemo_math::baked::register(&math.to_string())?;
    }
    if let Some(code) = baked.get("code") {
        kinemo_code::baked::register(&code.to_string())?;
    }
    Ok(())
}

/// Use the image `bytes` (PNG or JPEG) wherever the scene names `path` (`k.Image`).
#[wasm_bindgen]
pub fn add_image(path: &str, bytes: Vec<u8>) -> Result<(), JsError> {
    kinemo_render::media::register_bitmap(std::path::Path::new(path), bytes).map_err(|e| JsError::new(&e))
}

#[wasm_bindgen]
pub struct Player {
    scene: Scene,
    index: Arc<TimelineIndex>,
    options: RenderOptions,
}

#[wasm_bindgen]
impl Player {
    /// A player for the scene `ir` (the JSON a build writes), drawing `width`×`height` frames.
    #[wasm_bindgen(constructor)]
    pub fn new(ir: &str, width: u32, height: u32) -> Result<Player, JsError> {
        let scene: Scene = serde_json::from_str(ir)?;
        let index = Arc::new(TimelineIndex::new(&scene));
        let options = RenderOptions { width, height, fps: scene.config.fps, antialias: true, transparent: false };
        Ok(Player { scene, index, options })
    }

    pub fn duration(&self) -> f64 {
        self.scene.duration
    }

    /// The learner's answer: signal `signal` (a question's) takes `value`, an IR value as JSON
    /// (`{"Float": 3.5}`), for every frame from now on.
    pub fn set_signal(&mut self, signal: u32, value: &str) -> Result<(), JsError> {
        let value: kinemo_ir::Value = serde_json::from_str(value)?;
        let slot = self.scene.signals.get_mut(signal as usize).ok_or_else(|| JsError::new("no such signal"))?;
        slot.initial = value;
        self.index = Arc::new(TimelineIndex::new(&self.scene));
        Ok(())
    }

    /// Draw frames at another size from now on (the canvas was resized).
    pub fn resize(&mut self, width: u32, height: u32) {
        self.options.width = width;
        self.options.height = height;
    }

    /// The frame at `t` seconds, as RGBA bytes, row by row.
    pub fn render(&self, t: f64) -> Vec<u8> {
        rasterize(&self.display_list(t), self.options.antialias).rgba
    }

    /// The frame at `t` without its pixels: what the scene computes, for profiling.
    pub fn layout_only(&self, t: f64) -> usize {
        self.display_list(t).items.len()
    }
}

impl Player {
    fn display_list(&self, t: f64) -> DisplayList {
        let size = FrameSize { width: self.options.width, height: self.options.height };
        display_list_indexed(&self.scene, &self.index, t, size, self.options.transparent)
    }
}
