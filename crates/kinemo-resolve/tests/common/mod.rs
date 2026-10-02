//! IR scene builder for the visual-lint tests.
#![allow(dead_code)]

use kinemo_ir::{Blend, Ease, Entry, Expr, Lerp, Object, ObjectId, PlaceEntry, Placement, Scene, SceneConfig, Signal, SignalId, Span, Src, Value};
use kinemo_resolve::{run_visual_lints, LintFinding, LintOptions};

pub const WHITE: [f64; 4] = [1.0, 1.0, 1.0, 1.0];

pub struct SceneBuilder {
    pub scene: Scene,
}

impl SceneBuilder {
    /// 16 × 9 units at 1920 × 1080 (120 px/unit), dark background, `duration` seconds.
    pub fn new(duration: f64) -> Self {
        let mut scene = Scene::new(SceneConfig::default());
        scene.duration = duration;
        SceneBuilder { scene }
    }

    pub fn signal(&mut self, initial: Value) -> SignalId {
        let id = self.scene.signals.len() as SignalId;
        let lerp = if matches!(initial, Value::Str(_) | Value::Bool(_)) { Lerp::StepEnd } else { Lerp::Linear };
        self.scene.signals.push(Signal { id, initial, lerp, timeline: vec![], owner: None, span: Span::default() });
        id
    }

    /// Root object of `kind`, present from t=0, named `name`.
    pub fn object(&mut self, kind: &str, name: &str) -> ObjectId {
        let id = self.scene.objects.len() as ObjectId;
        self.scene.objects.push(Object {
            id,
            kind: kind.into(),
            name: Some(name.into()),
            presence: vec![(0.0, true)],
            span: Span { file: "scene.py".into(), line: id + 1, col: 0, ..Default::default() },
            ..Default::default()
        });
        self.scene.roots.push(id);
        id
    }

    pub fn prop(&mut self, obj: ObjectId, name: &str, value: Value) -> SignalId {
        let id = self.signal(value);
        self.scene.signals[id as usize].owner = Some((obj, name.into()));
        self.scene.objects[obj as usize].props.insert(name.into(), id);
        id
    }

    pub fn at(&mut self, obj: ObjectId, x: f64, y: f64) -> &mut Self {
        self.prop(obj, "x", Value::Float(x));
        self.prop(obj, "y", Value::Float(y));
        self
    }

    /// A `w` × `h` filled rectangle at (x, y).
    pub fn rect(&mut self, name: &str, w: f64, h: f64, x: f64, y: f64) -> ObjectId {
        let id = self.object("rect", name);
        self.prop(id, "w", Value::Float(w));
        self.prop(id, "h", Value::Float(h));
        self.prop(id, "fill", Value::Color(WHITE));
        self.prop(id, "fill_opacity", Value::Float(1.0));
        self.at(id, x, y);
        id
    }

    /// A white text of em `size` at (x, y).
    pub fn text(&mut self, name: &str, text: &str, size: f64, x: f64, y: f64) -> ObjectId {
        let id = self.object("text", name);
        self.prop(id, "text", Value::Str(text.into()));
        self.prop(id, "size", Value::Float(size));
        self.prop(id, "fill", Value::Color(WHITE));
        self.prop(id, "fill_opacity", Value::Float(1.0));
        self.at(id, x, y);
        id
    }

    pub fn animate(&mut self, obj: ObjectId, prop: &str, t0: f64, t1: f64, to: Value) -> &mut Self {
        let sid = match self.scene.prop(obj, prop) {
            Some(s) => s,
            None => self.prop(obj, prop, Value::Float(1.0)),
        };
        self.scene.signals[sid as usize].timeline.push(anim(t0, t1, to));
        self
    }

    pub fn bind(&mut self, obj: ObjectId, prop: &str, t: f64, e: Expr) -> &mut Self {
        let sid = self.scene.prop(obj, prop).unwrap_or_else(|| self.prop(obj, prop, Value::Float(0.0)));
        self.scene.signals[sid as usize].timeline.push(Entry::Set { t, src: Src::Expr { e }, span: Span::default() });
        self
    }

    pub fn place(&mut self, obj: ObjectId, p: Placement) -> &mut Self {
        self.scene.objects[obj as usize].place.push(PlaceEntry { t: 0.0, dur: 0.0, ease: Ease::Linear, p: Some(p), span: Default::default() });
        self
    }

    pub fn presence(&mut self, obj: ObjectId, toggles: Vec<(f64, bool)>) -> &mut Self {
        self.scene.objects[obj as usize].presence = toggles;
        self
    }

    pub fn lints(&self) -> Vec<LintFinding> {
        run_visual_lints(&self.scene, &LintOptions::default())
    }
}

pub fn anim(t0: f64, t1: f64, to: Value) -> Entry {
    Entry::Anim { t0, t1, to: Src::Val { v: to }, from: None, ease: Ease::Linear, blend: Blend::Replace, span: Span::default() }
}

pub fn at_anchor(anchor: &str) -> Placement {
    Placement {
        at: Some(anchor.into()),
        at_point: None,
        side: None,
        target: None,
        gap: None,
        margin: Some(Expr::Const { v: Value::Float(0.0) }),
        align: None,
        clamp: false,
        weak: false,
        rotated: false,
        span: Span { file: "scene.py".into(), line: 99, col: 0, ..Default::default() },
    }
}

/// Codes of the findings, in report order.
pub fn codes(findings: &[LintFinding]) -> Vec<&'static str> {
    findings.iter().map(|f| f.code.as_str()).collect()
}

pub fn only<'a>(findings: &'a [LintFinding], code: &str) -> Vec<&'a LintFinding> {
    findings.iter().filter(|f| f.code.as_str() == code).collect()
}
