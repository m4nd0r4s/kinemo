//! Visual lints (W10xx): readability problems found by sampling the timeline.
//!
//! Each lint family lives in its own module and implements [`VisualLint`]: it observes
//! every [`FrameSample`] and/or analyses the timeline directly, then reports
//! [`LintFinding`]s. [`run_visual_lints`] drives them and deduplicates findings per
//! `(code, objects)`, keeping the earliest instant.
//!
//! | Code  | Module           | Rule |
//! | ----- | ---------------- | ---- |
//! | W1001 | `safe_area`      | a visible leaf at rest extends past the frame inset by 0.5 u |
//! | W1002 | `overlap`        | two visible texts at rest overlap by > 10 % of the smaller box |
//! | W1003 | `contrast`       | text fill blended over the background has contrast < 4.5:1 |
//! | W1004 | `text_size`      | text em size < 18 px at the output resolution |
//! | W1005 | `invisible`      | a present, never-removed leaf stays invisible for > 3 s |
//! | W1006 | `noise`          | more than 12 simultaneous animations shorter than 0.3 s |
//! | W1007 | `static_scene`   | more than 8 s without any visual change |

mod contrast;
mod invisible;
mod noise;
mod overlap;
mod safe_area;
mod static_scene;
mod text_size;

use serde::Serialize;

use std::sync::Arc;

use kinemo_eval::{Evaluator, TimelineIndex};
use rayon::prelude::*;
use kinemo_ir::{ObjectId, Scene, SignalId, Span};
use kinemo_layout::Layout;

use crate::sampling::{expression_signals, sample_frame, sample_times, FrameSample, MotionIndex, DEFAULT_SAMPLE_STEP};

/// Thresholds of the visual lints. Defaults follow the spec.
#[derive(Clone, Debug, PartialEq)]
pub struct LintOptions {
    /// Uniform sampling step in seconds (timeline boundaries are always sampled too).
    pub sample_step: f64,
    /// Inset of the safe area from the frame edges, in scene units (W1001).
    pub safe_margin: f64,
    /// Overshoot below this (scene units) is ignored (W1001).
    pub safe_area_tolerance: f64,
    /// Minimum overlap as a fraction of the smaller text box (W1002).
    pub text_overlap_fraction: f64,
    /// Minimum WCAG contrast ratio (W1003).
    pub minimum_contrast: f64,
    /// Minimum text em size in output pixels (W1004).
    pub minimum_text_pixels: f64,
    /// Longest tolerated invisible stretch of a present object, in seconds (W1005).
    pub invisible_seconds: f64,
    /// Opacity at or below which an object counts as invisible (W1005).
    pub invisible_opacity: f64,
    /// Opacity above which an object counts as visible (W1001–W1004).
    pub visible_opacity: f64,
    /// Number of simultaneous short animations above which the scene is noisy (W1006).
    pub noise_animation_count: usize,
    /// Animations strictly shorter than this are "short" (W1006).
    pub noise_max_duration: f64,
    /// Longest tolerated stretch without visual change, in seconds (W1007).
    pub static_seconds: f64,
}

impl Default for LintOptions {
    fn default() -> Self {
        LintOptions {
            sample_step: DEFAULT_SAMPLE_STEP,
            safe_margin: 0.5,
            safe_area_tolerance: 1e-3,
            text_overlap_fraction: 0.10,
            minimum_contrast: 4.5,
            minimum_text_pixels: 18.0,
            invisible_seconds: 3.0,
            invisible_opacity: 0.01,
            visible_opacity: 0.05,
            noise_animation_count: 12,
            noise_max_duration: 0.3,
            static_seconds: 8.0,
        }
    }
}

impl LintOptions {
    pub fn with_step(step: f64) -> Self {
        LintOptions { sample_step: step, ..Default::default() }
    }
}

#[derive(Serialize, Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum LintCode {
    #[serde(rename = "W1001")]
    OutsideSafeArea,
    #[serde(rename = "W1002")]
    TextOverText,
    #[serde(rename = "W1003")]
    LowContrast,
    #[serde(rename = "W1004")]
    SmallText,
    #[serde(rename = "W1005")]
    InvisibleObject,
    #[serde(rename = "W1006")]
    VisualNoise,
    #[serde(rename = "W1007")]
    StaticScene,
}

impl LintCode {
    pub fn as_str(&self) -> &'static str {
        match self {
            LintCode::OutsideSafeArea => "W1001",
            LintCode::TextOverText => "W1002",
            LintCode::LowContrast => "W1003",
            LintCode::SmallText => "W1004",
            LintCode::InvisibleObject => "W1005",
            LintCode::VisualNoise => "W1006",
            LintCode::StaticScene => "W1007",
        }
    }
}

/// Frame edge an object crosses.
#[derive(Serialize, Clone, Copy, Debug, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum FrameEdge {
    Top,
    Bottom,
    Left,
    Right,
}

/// Why an object counts as invisible (W1005).
#[derive(Serialize, Clone, Copy, Debug, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum InvisibilityReason {
    /// Accumulated opacity ~0 (or nothing drawn yet).
    Transparent,
    /// World box entirely outside the frame.
    OutsideFrame,
    /// `visible=False` on the object or an ancestor.
    Hidden,
}

/// Lint-specific measurements, for messages and fixes.
#[derive(Serialize, Clone, Debug, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum LintDetails {
    /// `moving`: cut by the frame edge mid-animation, inside the safe area before and after;
    /// `reorder`: the motion is a container reordering its children (a swap arc).
    SafeArea { edge: FrameEdge, overshoot: f64, moving: bool, reorder: bool },
    TextOverlap { overlap_fraction: f64 },
    Contrast { ratio: f64, text_color: [f64; 3], background: [f64; 3] },
    TextSize { pixels: f64 },
    Invisible { duration: f64, reason: InvisibilityReason },
    Noise { simultaneous: usize },
    Static { duration: f64 },
}

/// Kind of fix the frontend can offer.
#[derive(Serialize, Clone, Debug, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum SuggestedFix {
    /// `target` (the leaf or an ancestor) is placed by a constraint: add `clamp=True` to it.
    ClampPlacement { target: ObjectId },
    /// `target` is free: give it a clamped placement, `.place(..., clamp=True)`.
    PlaceWithClamp { target: ObjectId },
}

#[derive(Serialize, Clone, Debug, PartialEq)]
pub struct LintFinding {
    pub code: LintCode,
    /// Objects involved, sorted (may be empty for scene-wide lints).
    pub objects: Vec<ObjectId>,
    /// First instant at which the problem shows.
    pub t: f64,
    /// Short message (Portuguese, with IR names; frontends may rebuild it from `details`).
    pub message: String,
    pub details: LintDetails,
    pub fix: Option<SuggestedFix>,
    /// Source location of the timeline entry behind the finding, when there is one
    /// (scene-wide lints); object lints are located by their objects.
    pub span: Option<Span>,
}

impl LintFinding {
    pub(crate) fn new(code: LintCode, mut objects: Vec<ObjectId>, t: f64, message: String, details: LintDetails) -> Self {
        objects.sort_unstable();
        objects.dedup();
        LintFinding { code, objects, t, message, details, fix: None, span: None }
    }
}

/// Shared, read-only inputs of every lint.
pub(crate) struct LintContext<'a> {
    pub scene: &'a Scene,
    pub options: &'a LintOptions,
}

/// A lint family. `observe` sees every sample in time order; `finish` reports.
pub(crate) trait VisualLint {
    fn observe(&mut self, _context: &LintContext, _sample: &FrameSample) {}
    fn finish(self: Box<Self>, context: &LintContext) -> Vec<LintFinding>;
}

/// Instants sampled together in parallel before the lints observe them.
const SAMPLE_BATCH: usize = 512;

/// Runs every visual lint over `scene`. Findings are deduplicated per `(code, objects)`
/// (earliest instant kept) and sorted by time, then code.
pub fn run_visual_lints(scene: &Scene, options: &LintOptions) -> Vec<LintFinding> {
    let context = LintContext { scene, options };
    let mut lints: Vec<Box<dyn VisualLint>> = vec![
        Box::new(safe_area::SafeAreaLint::default()),
        Box::new(overlap::TextOverlapLint::default()),
        Box::new(contrast::ContrastLint::default()),
        Box::new(text_size::TextSizeLint::default()),
        Box::new(invisible::InvisibleObjectLint::default()),
        Box::new(noise::VisualNoiseLint),
        Box::new(static_scene::StaticSceneLint::default()),
    ];
    let motion = MotionIndex::new(scene);
    let reactive = expression_signals(scene);
    let quiet = static_scene::quiet_stretches(scene, options.static_seconds);
    let in_quiet_stretch = |t: f64| quiet.iter().any(|&(from, to)| t >= from - options.sample_step && t <= to + options.sample_step);
    let index = Arc::new(TimelineIndex::new(scene));
    let times = sample_times(scene, options.sample_step);
    // Instants are sampled in parallel, a batch at a time (memory stays bounded); the lints
    // then observe them in time order, since some follow objects from one sample to the next.
    for batch in times.chunks(SAMPLE_BATCH) {
        let samples: Vec<FrameSample> = batch
            .par_iter()
            .map_init(
                || Evaluator::with_index(scene, index.clone()),
                |evaluator, &t| {
                    // One evaluator per worker, cleared per instant: memoization stays bounded
                    // and the caches keep their capacity.
                    evaluator.clear();
                    let layout = Layout::new(evaluator);
                    let reactive_now: &[SignalId] = if in_quiet_stretch(t) { &reactive } else { &[] };
                    sample_frame(&layout, &motion, reactive_now, t)
                },
            )
            .collect();
        for sample in &samples {
            for lint in lints.iter_mut() {
                lint.observe(&context, sample);
            }
        }
    }
    let findings: Vec<LintFinding> = lints.into_iter().flat_map(|lint| lint.finish(&context)).collect();
    deduplicate(findings)
}

fn deduplicate(mut findings: Vec<LintFinding>) -> Vec<LintFinding> {
    findings.sort_by(|a, b| a.t.total_cmp(&b.t).then(a.code.cmp(&b.code)));
    let mut out: Vec<LintFinding> = Vec::with_capacity(findings.len());
    for f in findings {
        if !out.iter().any(|o| o.code == f.code && o.objects == f.objects) {
            out.push(f);
        }
    }
    out
}

/// Records the first instant of each `(objects)` key; later observations are ignored.
#[derive(Default)]
pub(crate) struct FirstOccurrences {
    findings: Vec<LintFinding>,
}

impl FirstOccurrences {
    pub fn contains(&self, objects: &[ObjectId]) -> bool {
        self.findings.iter().any(|f| f.objects == objects)
    }

    pub fn record(&mut self, finding: LintFinding) {
        if !self.contains(&finding.objects) {
            self.findings.push(finding);
        }
    }

    pub fn into_findings(self) -> Vec<LintFinding> {
        self.findings
    }
}
