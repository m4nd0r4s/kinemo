//! Shared scene-building and inspection helpers for the render integration tests.
//!
//! Scenes are built directly as IR values: every prop is a signal, objects are present
//! from t=0 unless told otherwise, and roots are computed from the parent links. The
//! default test frame is 16 x 9 units rendered at 160 x 90 pixels (10 px per unit).
#![allow(dead_code)]

use kurbo::{BezPath, Rect, Shape};

use kinemo_ir::{Lerp, Object, ObjectId, Scene, SceneConfig, Signal, SignalId, Span, Value};
use kinemo_render::raster::{DisplayList, DrawItem, Image};
use kinemo_render::{display_list, render_frame, FrameSize, RenderOptions};

pub const SMALL_WIDTH: u32 = 160;
pub const SMALL_HEIGHT: u32 = 90;

pub const RED: [f64; 4] = [1.0, 0.0, 0.0, 1.0];
pub const GREEN: [f64; 4] = [0.0, 1.0, 0.0, 1.0];
pub const BLUE: [f64; 4] = [0.0, 0.0, 1.0, 1.0];
pub const BLACK: [f64; 4] = [0.0, 0.0, 0.0, 1.0];

/// Fluent builder of IR scenes for render tests.
pub struct SceneBuilder {
    scene: Scene,
}

impl Default for SceneBuilder {
    fn default() -> Self {
        Self::new()
    }
}

impl SceneBuilder {
    /// A 16 x 9 unit scene with a black background.
    pub fn new() -> Self {
        let config = SceneConfig { background: BLACK, ..SceneConfig::default() };
        SceneBuilder { scene: Scene::new(config) }
    }

    pub fn background(&mut self, color: [f64; 4]) -> &mut Self {
        self.scene.config.background = color;
        self
    }

    fn signal(&mut self, initial: Value, lerp: Lerp) -> SignalId {
        let id = self.scene.signals.len() as SignalId;
        self.scene.signals.push(Signal { id, initial, lerp, timeline: vec![], owner: None, span: Span::default() });
        id
    }

    /// Adds an object of `kind`, present from t=0.
    pub fn object(&mut self, kind: &str) -> ObjectId {
        let id = self.scene.objects.len() as ObjectId;
        self.scene.objects.push(Object { id, kind: kind.into(), presence: vec![(0.0, true)], ..Default::default() });
        id
    }

    /// Sets a prop (as a new signal with `value` as its initial value).
    pub fn prop(&mut self, obj: ObjectId, name: &str, value: Value) -> &mut Self {
        let lerp = if matches!(value, Value::Str(_) | Value::Bool(_)) { Lerp::StepEnd } else { Lerp::Linear };
        let id = self.signal(value, lerp);
        self.scene.signals[id as usize].owner = Some((obj, name.into()));
        self.scene.objects[obj as usize].props.insert(name.into(), id);
        self
    }

    pub fn prop_f(&mut self, obj: ObjectId, name: &str, value: f64) -> &mut Self {
        self.prop(obj, name, Value::Float(value))
    }

    /// A `w` x `h` rectangle centered on its origin, without paint.
    pub fn rect(&mut self, w: f64, h: f64) -> ObjectId {
        let id = self.object("rect");
        self.prop_f(id, "w", w).prop_f(id, "h", h);
        id
    }

    /// A `w` x `h` rectangle filled with `color` at full fill opacity.
    pub fn filled_rect(&mut self, w: f64, h: f64, color: [f64; 4]) -> ObjectId {
        let id = self.rect(w, h);
        self.fill(id, color);
        id
    }

    pub fn fill(&mut self, obj: ObjectId, color: [f64; 4]) -> &mut Self {
        self.prop(obj, "fill", Value::Color(color)).prop_f(obj, "fill_opacity", 1.0)
    }

    /// Stroke with `width` given in pixels at 1080p.
    pub fn stroke(&mut self, obj: ObjectId, color: [f64; 4], width: f64) -> &mut Self {
        self.prop(obj, "stroke", Value::Color(color)).prop_f(obj, "stroke_width", width)
    }

    /// Free position of `obj` in its parent's coordinates (scene units, y up).
    pub fn at(&mut self, obj: ObjectId, x: f64, y: f64) -> &mut Self {
        self.prop_f(obj, "x", x).prop_f(obj, "y", y)
    }

    /// A straight line from `start` to `end` (scene units).
    pub fn line(&mut self, start: [f64; 2], end: [f64; 2]) -> ObjectId {
        let id = self.object("line");
        self.prop(id, "start", Value::Vec2(start)).prop(id, "end", Value::Vec2(end));
        id
    }

    /// A filled text object.
    pub fn text(&mut self, text: &str, color: [f64; 4]) -> ObjectId {
        let id = self.object("text");
        self.prop(id, "text", Value::Str(text.into()));
        self.fill(id, color);
        id
    }

    /// A group holding `children`, in that order.
    pub fn group(&mut self, children: &[ObjectId]) -> ObjectId {
        let id = self.object("group");
        let list = Value::List(children.iter().map(|&c| Value::Object(c)).collect());
        let sig = self.signal(list, Lerp::Layout);
        self.scene.signals[sig as usize].owner = Some((id, "children".into()));
        self.scene.objects[id as usize].children = Some(sig);
        for &c in children {
            self.scene.objects[c as usize].parent = Some(id);
        }
        id
    }

    pub fn presence(&mut self, obj: ObjectId, toggles: Vec<(f64, bool)>) -> &mut Self {
        self.scene.objects[obj as usize].presence = toggles;
        self
    }

    pub fn build(mut self) -> Scene {
        self.scene.roots = self.scene.objects.iter().filter(|o| o.parent.is_none()).map(|o| o.id).collect();
        self.scene.duration = 10.0;
        self.scene
    }
}

pub fn small_size() -> FrameSize {
    FrameSize { width: SMALL_WIDTH, height: SMALL_HEIGHT }
}

/// Display list at `t` for the 160 x 90 test output.
pub fn small_display_list(scene: &Scene, t: f64) -> DisplayList {
    display_list(scene, t, small_size(), false)
}

pub fn small_render_options(transparent: bool) -> RenderOptions {
    RenderOptions { width: SMALL_WIDTH, height: SMALL_HEIGHT, fps: 30.0, antialias: false, transparent }
}

/// Renders `scene` at `t` to a 160 x 90 image without antialiasing.
pub fn render_small(scene: &Scene, t: f64, transparent: bool) -> Image {
    render_frame(scene, t, &small_render_options(transparent))
}

/// RGBA of the pixel at column `x`, row `y` (y down).
pub fn pixel(img: &Image, x: u32, y: u32) -> [u8; 4] {
    let i = ((y * img.width + x) * 4) as usize;
    img.rgba[i..i + 4].try_into().unwrap()
}

pub fn to_rgba8(c: [f64; 4]) -> [u8; 4] {
    c.map(|v| (v * 255.0).round() as u8)
}

/// Fill color of every item, in draw order (`None` for stroke-only items).
pub fn fill_colors(dl: &DisplayList) -> Vec<Option<[f64; 4]>> {
    dl.items.iter().map(|i| i.fill.as_ref().map(|f| f.color)).collect()
}

pub fn path_bbox(path: &BezPath) -> Rect {
    path.bounding_box()
}

pub fn item_length(item: &DrawItem) -> f64 {
    kinemo_render::geom::path_length(&item.path)
}

pub fn assert_near(actual: f64, expected: f64, tolerance: f64) {
    assert!((actual - expected).abs() <= tolerance, "expected {expected} ± {tolerance}, got {actual}");
}
