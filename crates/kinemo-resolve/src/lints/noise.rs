//! W1006: visual noise — more than 12 animations shorter than 0.3 s running at once.
//!
//! An "animation" is one object animated over one interval: the entries of all props of
//! the same object with the same `[t0, t1]` count once (`obj.to(x=, y=)` is one
//! animation); entries of free signals count per signal. Concurrency is computed exactly
//! with a sweep over the intervals (open intervals: back-to-back animations do not
//! overlap), so it does not depend on the sampling step. One finding per burst.

use std::collections::BTreeSet;

use kinemo_ir::{Entry, ObjectId, Span};

use super::{LintCode, LintContext, LintDetails, LintFinding, VisualLint};

pub(crate) struct VisualNoiseLint;

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord)]
enum Animated {
    Object(ObjectId),
    FreeSignal(u32),
}

struct ShortAnimation {
    who: Animated,
    t0: f64,
    t1: f64,
    span: Span,
}

fn short_animations(context: &LintContext) -> Vec<ShortAnimation> {
    let max = context.options.noise_max_duration;
    let mut out: Vec<ShortAnimation> = Vec::new();
    for signal in &context.scene.signals {
        let who = match &signal.owner {
            Some((o, _)) => Animated::Object(*o),
            None => Animated::FreeSignal(signal.id),
        };
        for entry in &signal.timeline {
            let Entry::Anim { t0, t1, span, .. } = entry else { continue };
            let duration = t1 - t0;
            if duration <= 0.0 || duration >= max {
                continue;
            }
            let same = |a: &ShortAnimation| a.who == who && a.t0 == *t0 && a.t1 == *t1;
            if !out.iter().any(same) {
                out.push(ShortAnimation { who: who.clone(), t0: *t0, t1: *t1, span: span.clone() });
            }
        }
    }
    out
}

impl VisualLint for VisualNoiseLint {
    fn finish(self: Box<Self>, context: &LintContext) -> Vec<LintFinding> {
        let animations = short_animations(context);
        // Sweep events: (time, is_start, index). Ends sort before starts at the same time.
        let mut events: Vec<(f64, bool, usize)> = Vec::with_capacity(animations.len() * 2);
        for (i, a) in animations.iter().enumerate() {
            events.push((a.t0, true, i));
            events.push((a.t1, false, i));
        }
        events.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.cmp(&b.1)));
        let limit = context.options.noise_animation_count;
        let mut active: BTreeSet<usize> = BTreeSet::new();
        let mut in_burst = false;
        let mut findings = Vec::new();
        for (t, is_start, i) in events {
            if is_start {
                active.insert(i);
            } else {
                active.remove(&i);
            }
            if active.len() > limit && !in_burst {
                in_burst = true;
                let objects: Vec<ObjectId> = active
                    .iter()
                    .filter_map(|&j| match animations[j].who {
                        Animated::Object(o) => Some(o),
                        Animated::FreeSignal(_) => None,
                    })
                    .collect();
                let first = active.iter().next().map(|&j| animations[j].span.clone());
                let message = format!(
                    "{} short animations (< {:.1} s) at the same time",
                    active.len(),
                    context.options.noise_max_duration
                );
                let mut finding = LintFinding::new(
                    LintCode::VisualNoise,
                    objects,
                    t,
                    message,
                    LintDetails::Noise { simultaneous: active.len() },
                );
                finding.span = first;
                findings.push(finding);
            } else if active.len() <= limit {
                in_burst = false;
            }
        }
        findings
    }
}
