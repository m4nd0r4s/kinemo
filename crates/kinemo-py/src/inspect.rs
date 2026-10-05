//! Scene-graph snapshots for `kinemo inspect` and layout diagnostics for `check`.

use pyo3::prelude::*;
use serde_json::{json, Value as Json};

use kinemo_layout::LayoutIssueKind;
use kinemo_render::inspect::object_json;

use crate::builder::{layout_at, Builder};
use crate::errors::to_json;

#[pymethods]
impl Builder {
    /// JSON snapshot of every object at `t`.
    fn inspect(&self, t: f64) -> String {
        self.with_layout(|l| {
            let objects: Vec<Json> =
                (0..l.scene().objects.len() as u32).map(|o| object_json(l, o, t)).collect();
            to_json(&objects)
        })
    }

    /// World bounding boxes of the given objects at `t`: [[x0, y0, x1, y1], ...].
    fn world_bboxes(&self, objects: Vec<u32>, t: f64) -> Vec<[f64; 4]> {
        self.with_layout(|l| {
            objects
                .iter()
                .map(|&o| {
                    let b = l.world_bbox(o, t);
                    [b.x0, b.y0, b.x1, b.y1]
                })
                .collect()
        })
    }

    /// Layout problems found when resolving every object at each of `times`.
    fn layout_issues(&self, py: Python<'_>, times: Vec<f64>) -> String {
        let mut out: Vec<Json> = vec![];
        let scene = &self.scene;
        let issues_at = py.detach(|| {
            layout_at(scene, &times, |l, t| {
                for o in 0..l.scene().objects.len() as u32 {
                    l.translation(o, t);
                }
                l.issues()
            })
        });
        for issue in issues_at.into_iter().flatten() {
            let code = match issue.kind {
                LayoutIssueKind::Cycle => "K0402",
                LayoutIssueKind::Contradiction => "K0403",
            };
            if !out.iter().any(|j| j["code"] == code && j["objects"] == json!(issue.objects)) {
                out.push(json!({"code": code, "objects": issue.objects, "t": issue.t}));
            }
        }
        to_json(&out)
    }
}
