//! W1007: more than 8 s without any visual change.
//!
//! Approximation: the scene "changes" while any animation entry is active (`[t0, t1]`
//! of every `Anim`, on any signal), at every `Set`, presence toggle and placement change,
//! and between two consecutive samples where any expression-driven signal (a live
//! binding: `k.time`, lambdas, `place(at=obj.point)` ...) takes a different value. The
//! last test is sampled, so changes shorter than the sampling step can be missed, and a
//! change that is invisible on screen (an animated free signal nobody reads) still
//! counts as a change. Gaps between changes in `[0, duration]` longer than 8 s are reported
//! at their start, located at the timeline entry that ended right before the gap.

use kinemo_ir::{Entry, SignalId, Span, Value};
use kinemo_layout::Layout;

use super::{LintCode, LintContext, LintDetails, LintFinding, VisualLint};
use crate::sampling::{values_close, FrameSample};

#[derive(Default)]
pub(crate) struct StaticSceneLint {
    previous: Option<(f64, Vec<(SignalId, Value)>)>,
    /// Intervals during which a reactive (expression-driven) value changed.
    reactive_changes: Vec<(f64, f64)>,
}

/// A stretch of the timeline during which something changes.
struct Change {
    start: f64,
    end: f64,
    span: Option<Span>,
}

impl VisualLint for StaticSceneLint {
    fn observe(&mut self, _context: &LintContext, sample: &FrameSample, _layout: &Layout) {
        if let Some((t_prev, values)) = &self.previous {
            let changed = values
                .iter()
                .zip(&sample.reactive_values)
                .any(|((_, before), (_, after))| !values_close(before, after));
            if changed {
                self.reactive_changes.push((*t_prev, sample.t));
            }
        }
        self.previous = Some((sample.t, sample.reactive_values.clone()));
    }

    fn finish(self: Box<Self>, context: &LintContext) -> Vec<LintFinding> {
        let scene = context.scene;
        let mut changes: Vec<Change> = Vec::new();
        for signal in &scene.signals {
            for entry in &signal.timeline {
                let span = match entry {
                    Entry::Set { span, .. } | Entry::Anim { span, .. } => span.clone(),
                };
                changes.push(Change { start: entry.start(), end: entry.end(), span: Some(span) });
            }
        }
        for object in &scene.objects {
            for (t, _) in &object.presence {
                changes.push(Change { start: *t, end: *t, span: Some(object.span.clone()) });
            }
            for e in &object.place {
                let span = e.p.as_ref().map(|p| p.span.clone()).unwrap_or_else(|| object.span.clone());
                changes.push(Change { start: e.t, end: e.t + e.dur, span: Some(span) });
            }
        }
        changes.extend(self.reactive_changes.iter().map(|&(start, end)| Change { start, end, span: None }));
        changes.sort_by(|a, b| a.start.total_cmp(&b.start));

        let limit = context.options.static_seconds;
        let mut findings = Vec::new();
        let mut covered_until = 0.0_f64;
        let mut last_span: Option<Span> = None;
        let report = |from: f64, to: f64, span: &Option<Span>, findings: &mut Vec<LintFinding>| {
            let duration = to - from;
            if duration > limit {
                let message = format!("{duration:.1} s without any visual change");
                let mut f = LintFinding::new(LintCode::StaticScene, vec![], from, message, LintDetails::Static { duration });
                f.span = span.clone();
                findings.push(f);
            }
        };
        for c in &changes {
            if c.start > covered_until {
                report(covered_until, c.start.min(scene.duration), &last_span, &mut findings);
            }
            if c.end >= covered_until {
                covered_until = c.end;
                if c.span.is_some() {
                    last_span = c.span.clone();
                }
            }
        }
        if scene.duration > covered_until {
            report(covered_until, scene.duration, &last_span, &mut findings);
        }
        findings
    }
}
