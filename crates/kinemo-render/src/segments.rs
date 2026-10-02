//! Timeline segments and their content hashes, for frame caches.
//!
//! A segment is an interval between consecutive changes (animation boundaries, presence
//! toggles, placement changes). Its hash covers the static scene plus every timed IR item
//! that starts before the segment ends, so editing the end of a scene keeps the hashes
//! (and cached frames) of everything before the edit.

use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

use kinemo_ir::{Entry, Scene};

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Segment {
    pub start: f64,
    pub end: f64,
    pub hash: u64,
}

fn hash_of<T: serde::Serialize>(value: &T) -> u64 {
    let mut h = DefaultHasher::new();
    serde_json::to_string(value).unwrap_or_default().hash(&mut h);
    h.finish()
}

fn combine(a: u64, b: u64) -> u64 {
    let mut h = DefaultHasher::new();
    (a, b).hash(&mut h);
    h.finish()
}

/// (start time, hash) of every timed item of the scene.
fn timed_items(scene: &Scene) -> Vec<(f64, u64)> {
    let mut items = Vec::new();
    for s in &scene.signals {
        for (i, e) in s.timeline.iter().enumerate() {
            let start = match e {
                Entry::Set { t, .. } => *t,
                Entry::Anim { t0, .. } => *t0,
            };
            items.push((start, combine(hash_of(&(s.id, i)), hash_of(e))));
        }
    }
    for o in &scene.objects {
        for (t, present) in &o.presence {
            items.push((*t, hash_of(&(o.id, "presence", t.to_bits(), present))));
        }
        for p in &o.place {
            items.push((p.t, combine(hash_of(&(o.id, "place")), hash_of(p))));
        }
    }
    items.sort_by(|a, b| a.0.total_cmp(&b.0).then(a.1.cmp(&b.1)));
    items
}

fn boundaries(scene: &Scene) -> Vec<f64> {
    let mut times = vec![0.0, scene.duration];
    for s in &scene.signals {
        for e in &s.timeline {
            times.push(e.start());
            times.push(e.end());
        }
    }
    for o in &scene.objects {
        times.extend(o.presence.iter().map(|(t, _)| *t));
        for p in &o.place {
            times.push(p.t);
            times.push(p.t + p.dur);
        }
    }
    times.retain(|t| t.is_finite() && *t >= 0.0 && *t <= scene.duration);
    times.sort_by(f64::total_cmp);
    times.dedup_by(|a, b| (*a - *b).abs() < 1e-9);
    times
}

/// Segments covering `[0, duration]` in order.
pub fn segments(scene: &Scene) -> Vec<Segment> {
    let mut statics = DefaultHasher::new();
    hash_of(&scene.config).hash(&mut statics);
    for o in &scene.objects {
        hash_of(&(&o.kind, o.parent, o.children, &o.props)).hash(&mut statics);
    }
    // Initial values hold most static props (a radius, a text's content); spans are left
    // out so moving code around keeps the cache.
    for s in &scene.signals {
        hash_of(&(s.id, &s.initial, &s.lerp, &s.owner)).hash(&mut statics);
    }
    hash_of(&(&scene.tables, &scene.roots)).hash(&mut statics);
    let mut running = statics.finish();
    let items = timed_items(scene);
    let mut next = 0;
    let times = boundaries(scene);
    let mut out = Vec::with_capacity(times.len());
    for w in times.windows(2) {
        let (start, end) = (w[0], w[1]);
        while next < items.len() && items[next].0 < end {
            running = combine(running, items[next].1);
            next += 1;
        }
        out.push(Segment { start, end, hash: running });
    }
    if out.is_empty() {
        out.push(Segment { start: 0.0, end: scene.duration, hash: running });
    }
    out
}

/// Hash of the segment containing `t`.
pub fn segment_hash_at(segments: &[Segment], t: f64) -> u64 {
    let i = segments.partition_point(|s| s.end <= t).min(segments.len().saturating_sub(1));
    segments.get(i).map_or(0, |s| s.hash)
}

#[cfg(test)]
mod tests {
    use super::*;
    use kinemo_ir::{Ease, Signal, Src, Value, SceneConfig, Blend, Span, Lerp};

    fn anim(t0: f64, t1: f64) -> Entry {
        Entry::Anim { t0, t1, to: Src::Val { v: Value::Float(1.0) }, from: None, ease: Ease::Linear, blend: Blend::Replace, span: Span::default() }
    }

    fn scene(entries: Vec<Entry>) -> Scene {
        let mut s = Scene::new(SceneConfig::default());
        s.duration = 10.0;
        s.signals.push(Signal { id: 0, initial: Value::Float(0.0), lerp: Lerp::Linear, timeline: entries, owner: None, span: Span::default() });
        s
    }

    #[test]
    fn editing_the_end_keeps_earlier_hashes() {
        let a = segments(&scene(vec![anim(0.0, 1.0), anim(5.0, 6.0)]));
        let b = segments(&scene(vec![anim(0.0, 1.0), anim(5.0, 7.0)]));
        assert_eq!(segment_hash_at(&a, 0.5), segment_hash_at(&b, 0.5));
        assert_eq!(segment_hash_at(&a, 3.0), segment_hash_at(&b, 3.0));
        assert_ne!(segment_hash_at(&a, 5.5), segment_hash_at(&b, 5.5));
    }

    #[test]
    fn changing_an_initial_value_changes_every_hash() {
        let a = segments(&scene(vec![anim(5.0, 6.0)]));
        let mut changed = scene(vec![anim(5.0, 6.0)]);
        changed.signals[0].initial = Value::Float(0.5);
        let b = segments(&changed);
        assert_ne!(segment_hash_at(&a, 0.5), segment_hash_at(&b, 0.5));
        assert_ne!(segment_hash_at(&a, 8.0), segment_hash_at(&b, 8.0));
    }

    #[test]
    fn segments_cover_the_scene() {
        let s = segments(&scene(vec![anim(1.0, 2.0)]));
        assert_eq!(s.first().unwrap().start, 0.0);
        assert_eq!(s.last().unwrap().end, 10.0);
    }
}
