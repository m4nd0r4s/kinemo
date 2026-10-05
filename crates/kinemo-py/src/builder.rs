//! Incremental IR builder used by the Python build phase.

use pyo3::prelude::*;

use std::sync::Arc;

use kinemo_eval::{Evaluator, TimelineIndex};
use kinemo_ir::{
    Audio, AudioRole, Entry, Expr, Lerp, Mark, Object, PlaceEntry, Scene, SceneConfig, Signal, Span,
    Table, Value,
};
use kinemo_layout::Layout;

use crate::errors::{parse, to_json};
use kinemo_ir::retime::{remap, Op, Warp};

#[pyclass(module = "kinemo._core")]
pub struct Builder {
    pub(crate) scene: Scene,
    log: Vec<Op>,
    snapshots: Vec<(Scene, usize)>,
}

/// Tolerance for touching time intervals (sequenced animations share an endpoint).
const EPS: f64 = 1e-9;

fn lerp_mode(name: &str) -> PyResult<Lerp> {
    parse("lerp mode", &format!("\"{name}\""))
}

impl Builder {
    pub(crate) fn with_layout<T>(&self, f: impl FnOnce(&Layout) -> T) -> T {
        let ev = Evaluator::new(&self.scene);
        let layout = Layout::new(&ev);
        f(&layout)
    }

    /// [`Builder::with_layout`] at many instants: a fresh evaluator per instant (memoization
    /// stays bounded) sharing the time-independent timeline work.
    pub(crate) fn with_layout_at<T>(&self, times: impl IntoIterator<Item = f64>, mut f: impl FnMut(&Layout, f64) -> T) -> Vec<T> {
        let index = Arc::new(TimelineIndex::new(&self.scene));
        times
            .into_iter()
            .map(|t| {
                let ev = Evaluator::with_index(&self.scene, index.clone());
                let layout = Layout::new(&ev);
                f(&layout, t)
            })
            .collect()
    }
}

#[pymethods]
impl Builder {
    #[new]
    fn new(config_json: &str) -> PyResult<Self> {
        let config: SceneConfig = parse("scene config", config_json)?;
        Ok(Builder { scene: Scene::new(config), log: vec![], snapshots: vec![] })
    }

    // ---- construction -------------------------------------------------------------

    #[pyo3(signature = (initial_json, lerp = "linear", owner = None, span_json = None))]
    fn add_signal(
        &mut self,
        initial_json: &str,
        lerp: &str,
        owner: Option<(u32, String)>,
        span_json: Option<&str>,
    ) -> PyResult<u32> {
        let id = self.scene.signals.len() as u32;
        let span: Span = span_json.map(|s| parse("span", s)).transpose()?.unwrap_or_default();
        self.scene.signals.push(Signal {
            id,
            initial: parse("value", initial_json)?,
            lerp: lerp_mode(lerp)?,
            timeline: vec![],
            owner,
            span,
        });
        Ok(id)
    }

    fn push_entry(&mut self, signal: u32, entry_json: &str) -> PyResult<()> {
        let entry: Entry = parse("timeline entry", entry_json)?;
        let timeline = &mut self.scene.signals[signal as usize].timeline;
        timeline.push(entry);
        self.log.push(Op::Entry { signal, index: timeline.len() - 1 });
        Ok(())
    }

    #[pyo3(signature = (kind, span_json, name = None))]
    fn add_object(&mut self, kind: &str, span_json: &str, name: Option<String>) -> PyResult<u32> {
        let id = self.scene.objects.len() as u32;
        self.scene.objects.push(Object {
            id,
            kind: kind.into(),
            name,
            span: parse("span", span_json)?,
            ..Default::default()
        });
        Ok(id)
    }

    fn set_name(&mut self, obj: u32, name: String) {
        self.scene.objects[obj as usize].name = Some(name);
    }

    fn set_prop(&mut self, obj: u32, name: String, signal: u32) {
        self.scene.objects[obj as usize].props.insert(name, signal);
    }

    fn set_children_signal(&mut self, obj: u32, signal: u32) {
        self.scene.objects[obj as usize].children = Some(signal);
    }

    fn set_parent(&mut self, child: u32, parent: Option<u32>) {
        self.scene.objects[child as usize].parent = parent;
        self.scene.roots.retain(|r| *r != child);
        if parent.is_none() {
            self.scene.roots.push(child);
        }
    }

    fn add_root(&mut self, obj: u32) {
        if !self.scene.roots.contains(&obj) {
            self.scene.roots.push(obj);
        }
    }

    /// Move a root to the end of the draw order (objects entering later draw on top).
    fn raise_root(&mut self, obj: u32) {
        if let Some(index) = self.scene.roots.iter().position(|r| *r == obj) {
            let root = self.scene.roots.remove(index);
            self.scene.roots.push(root);
        }
    }

    fn set_presence(&mut self, obj: u32, t: f64, present: bool) {
        let presence = &mut self.scene.objects[obj as usize].presence;
        // Keep toggles sorted; same-time toggles keep insertion order.
        let index = presence.iter().rposition(|(pt, _)| *pt <= t).map_or(0, |i| i + 1);
        presence.insert(index, (t, present));
        for op in self.log.iter_mut() {
            if let Op::Presence { object, index: i } = op {
                if *object == obj && *i >= index {
                    *i += 1;
                }
            }
        }
        self.log.push(Op::Presence { object: obj, index });
    }

    fn push_place(&mut self, obj: u32, entry_json: &str) -> PyResult<()> {
        let entry: PlaceEntry = parse("placement", entry_json)?;
        let place = &mut self.scene.objects[obj as usize].place;
        let index = place.iter().rposition(|e| e.t <= entry.t).map_or(0, |i| i + 1);
        place.insert(index, entry);
        for op in self.log.iter_mut() {
            if let Op::Place { object, index: i } = op {
                if *object == obj && *i >= index {
                    *i += 1;
                }
            }
        }
        self.log.push(Op::Place { object: obj, index });
        Ok(())
    }

    #[pyo3(signature = (t, name = None, slide = false))]
    fn add_mark(&mut self, t: f64, name: Option<String>, slide: bool) {
        self.scene.marks.push(Mark { name, t, slide });
        self.log.push(Op::Mark { index: self.scene.marks.len() - 1 });
    }

    #[pyo3(signature = (path, t, gain = 1.0, role = "sound", duck = 0.0, fade = 0.0))]
    fn add_audio(&mut self, path: String, t: f64, gain: f64, role: &str, duck: f64, fade: f64) {
        let role = match role {
            "voice" => AudioRole::Voice,
            "music" => AudioRole::Music,
            _ => AudioRole::Sound,
        };
        self.scene.audio.push(Audio { path, t, gain, role, duck, fade });
        self.log.push(Op::Audio { index: self.scene.audio.len() - 1 });
    }

    /// Reserves a precomputed table (filled at the end of the build).
    fn add_table(&mut self) -> u32 {
        self.scene.tables.push(Table { t0: 0.0, dt: 1.0, values: vec![] });
        (self.scene.tables.len() - 1) as u32
    }

    fn set_table(&mut self, id: u32, t0: f64, dt: f64, values: Vec<f64>) {
        self.scene.tables[id as usize] = Table { t0, dt, values };
    }

    fn set_duration(&mut self, duration: f64) {
        self.scene.duration = duration;
    }

    #[getter]
    fn duration(&self) -> f64 {
        self.scene.duration
    }

    // ---- re-timing and rollback ---------------------------------------------------

    /// Current position in the op log (pass it to `remap` later).
    fn log_position(&self) -> usize {
        self.log.len()
    }

    /// Re-times everything inserted since `since` with a speed ramp from `f0` to `f1`
    /// over the local block `[t0, t0 + length]`. Returns the warped block end.
    fn remap(&mut self, since: usize, t0: f64, length: f64, f0: f64, f1: f64) -> f64 {
        let w = Warp { t0, len: length, f0, f1 };
        let ops: Vec<Op> = self.log[since..].to_vec();
        remap(&mut self.scene, &ops, w);
        w.apply(t0 + length)
    }

    fn warp_time(&self, t: f64, t0: f64, length: f64, f0: f64, f1: f64) -> f64 {
        Warp { t0, len: length, f0, f1 }.apply(t)
    }

    fn snapshot(&mut self) -> usize {
        self.snapshots.push((self.scene.clone(), self.log.len()));
        self.snapshots.len() - 1
    }

    /// Rolls back to snapshot `id`, keeping it (later snapshots are dropped).
    fn restore(&mut self, id: usize) {
        let (scene, log_len) = self.snapshots[id].clone();
        self.scene = scene;
        self.log.truncate(log_len);
        self.snapshots.truncate(id + 1);
    }

    fn drop_snapshot(&mut self, id: usize) {
        self.snapshots.truncate(id);
    }

    // ---- queries ------------------------------------------------------------------

    fn eval_signal(&self, signal: u32, t: f64) -> String {
        self.with_layout(|l| to_json(&l.evaluator().signal(signal, t, l)))
    }

    fn eval_expr(&self, expr_json: &str, t: f64) -> PyResult<String> {
        let e: Expr = parse("expression", expr_json)?;
        Ok(self.with_layout(|l| to_json(&l.evaluator().expr(&e, t, l))))
    }

    /// Numeric samples of an expression on a uniform time grid.
    fn eval_expr_grid(&self, expr_json: &str, t0: f64, dt: f64, n: usize) -> PyResult<Vec<f64>> {
        let e: Expr = parse("expression", expr_json)?;
        Ok(self.with_layout_at((0..n).map(|i| t0 + i as f64 * dt), |l, t| l.evaluator().expr(&e, t, l).as_f64()))
    }

    #[pyo3(signature = (obj, prop, t, world = false))]
    fn derived(&self, obj: u32, prop: &str, t: f64, world: bool) -> String {
        self.with_layout(|l| to_json(&l.derived(obj, prop, world, t)))
    }

    fn present(&self, obj: u32, t: f64) -> bool {
        self.scene.present(obj, t)
    }

    /// Outline of an object at `t` in world coordinates, flattened and resampled to `n`
    /// points evenly spaced by arc length (for `k.follow`).
    fn outline_points(&self, obj: u32, t: f64, n: usize) -> Vec<(f64, f64)> {
        self.with_layout(|l| {
            let to_world = l.render_affine(obj, t);
            let mut pts: Vec<kurbo::Point> = vec![];
            for part in l.parts(obj, t) {
                let path = to_world * part.path;
                kurbo::flatten(&path, 1e-3, |el| match el {
                    kurbo::PathEl::MoveTo(p) | kurbo::PathEl::LineTo(p) => pts.push(p),
                    kurbo::PathEl::ClosePath => {
                        if let Some(first) = pts.first().copied() {
                            pts.push(first);
                        }
                    }
                    _ => {}
                });
            }
            kinemo_render::geom::resample_points(&pts, n).into_iter().map(|p| (p.x, p.y)).collect()
        })
    }

    /// Glyphs of a text-like source at `t`: `[{key, char_index, line, word}, ...]` plus the
    /// plain text (markup removed), for addressing parts.
    fn glyph_info(&self, source: u32, t: f64) -> String {
        self.with_layout(|l| {
            let glyphs: Vec<serde_json::Value> = l
                .source_glyphs(source, t)
                .iter()
                .map(|g| serde_json::json!({"key": g.key, "char_index": g.char_index, "line": g.line, "word": g.word}))
                .collect();
            let text = l.prop_str(source, "text", t).unwrap_or_default();
            serde_json::json!({"text": text, "glyphs": glyphs}).to_string()
        })
    }

    /// Parts of a subtree as a morph pairs them: `[[key | null, [x, y]], ...]`.
    fn morph_parts(&self, root: u32, t: f64) -> String {
        to_json(&kinemo_render::morph_parts(&self.scene, root, t))
    }

    /// Expressions a signal is bound to over its timeline (for dependency analysis).
    fn signal_sources(&self, signal: u32) -> String {
        let exprs: Vec<&kinemo_ir::Expr> = self.scene.signals[signal as usize]
            .timeline
            .iter()
            .filter_map(|e| match e {
                Entry::Set { src: kinemo_ir::Src::Expr { e }, .. } | Entry::Anim { to: kinemo_ir::Src::Expr { e }, .. } => Some(e),
                _ => None,
            })
            .collect();
        to_json(&exprs)
    }

    /// Presence toggles of an object as JSON `[[t, present], ...]`.
    fn object_presence(&self, obj: u32) -> String {
        to_json(&self.scene.objects[obj as usize].presence)
    }

    /// Time of the last exit of `obj` at or before `t`, if any.
    fn last_exit(&self, obj: u32, t: f64) -> Option<f64> {
        self.scene.objects[obj as usize]
            .presence
            .iter()
            .filter(|(pt, p)| *pt <= t && !*p)
            .map(|(pt, _)| *pt)
            .next_back()
    }

    /// Span of a Replace animation on `signal` overlapping `[t0, t1)`, if any.
    fn overlapping_anim(&self, signal: u32, t0: f64, t1: f64) -> Option<String> {
        self.scene.signals[signal as usize].timeline.iter().find_map(|e| match e {
            Entry::Anim { t0: a0, t1: a1, blend: kinemo_ir::Blend::Replace, span, .. }
                if *a0 < t1 - EPS && t0 < *a1 - EPS && a1 > a0 =>
            {
                Some(to_json(&(span, *a0, *a1)))
            }
            _ => None,
        })
    }

    fn signal_count(&self) -> usize {
        self.scene.signals.len()
    }

    fn to_json(&self) -> String {
        self.scene.to_json()
    }

    fn value_kind(&self, signal: u32) -> &'static str {
        match self.scene.signals[signal as usize].initial {
            Value::Float(_) => "float",
            Value::Int(_) => "int",
            Value::Bool(_) => "bool",
            Value::Str(_) => "str",
            Value::Vec2(_) => "vec2",
            Value::Color(_) => "color",
            Value::List(_) => "list",
            Value::Object(_) => "object",
            Value::None => "none",
        }
    }
}
