//! Branches of a lesson's questions (`s.ask`): each branch is built after the previous one on
//! the same timeline, so at its boundaries everything a branch touched is put back the way it
//! was at the question (or at the end of the correct branch, where the lesson continues).

use std::collections::BTreeSet;

use pyo3::prelude::*;

use kinemo_eval::Evaluator;
use kinemo_ir::retime::Op;
use kinemo_ir::{Blend, Entry, PlaceEntry, Question, Scene, SignalId, Span, Src};
use kinemo_layout::Layout;

use crate::builder::Builder;
use crate::errors::{parse, to_json};

/// What a signal follows at `t` in `scene`: its binding when a constant set put one there,
/// otherwise the value it has then.
fn source_at(scene: &Scene, layout: &Layout, signal: SignalId, t: f64) -> Src {
    let timeline = &scene.signal(signal).timeline;
    let started = |e: &&Entry| e.start() <= t + 1e-9;
    let additive = timeline.iter().filter(started).any(|e| matches!(e, Entry::Anim { blend: Blend::Add, .. }));
    // The entry in force: the latest to start (on a tie, the one written last).
    let latest = timeline.iter().filter(started).enumerate().max_by(|(i, a), (j, b)| a.start().total_cmp(&b.start()).then(i.cmp(j)));
    if let (false, Some((_, Entry::Set { src: Src::Expr { e }, .. }))) = (additive, latest) {
        return Src::Expr { e: e.clone() };
    }
    Src::Val { v: layout.evaluator().signal(signal, t, layout) }
}

#[pymethods]
impl Builder {
    /// Keep a copy of the scene as it is now; `reset_touched` reads states from it.
    fn freeze(&mut self) -> usize {
        self.frozen.push(self.scene.clone());
        self.frozen.len() - 1
    }

    /// At `t`, puts everything written since log position `since` (signals, presence,
    /// placement) back the way frozen copy `frozen` had it at `reference`. Returns the
    /// `[signal, source]` pairs it set, as JSON (the Python side keeps them as bases).
    fn reset_touched(&mut self, frozen: usize, since: usize, reference: f64, t: f64) -> String {
        let mut signals = BTreeSet::new();
        let mut presence = BTreeSet::new();
        let mut places = BTreeSet::new();
        for op in &self.log[since..] {
            match op {
                Op::Entry { signal, .. } => {
                    signals.insert(*signal);
                }
                Op::Presence { object, .. } => {
                    presence.insert(*object);
                }
                Op::Place { object, .. } => {
                    places.insert(*object);
                }
                Op::Mark { .. } | Op::Audio { .. } => {}
            }
        }
        let then = &self.frozen[frozen];
        // Signals and objects made after the freeze did not exist then: absent, nothing to restore.
        let sources: Vec<(SignalId, Src)> = {
            let evaluator = Evaluator::new(then);
            let layout = Layout::new(&evaluator);
            signals.into_iter().filter(|s| (*s as usize) < then.signals.len()).map(|s| (s, source_at(then, &layout, s, reference))).collect()
        };
        let present: Vec<(u32, bool)> =
            presence.into_iter().map(|o| (o, (o as usize) < then.objects.len() && then.present(o, reference))).collect();
        let placed: Vec<(u32, Option<kinemo_ir::Placement>)> = places
            .into_iter()
            .map(|o| {
                let entries = then.objects.get(o as usize).map_or(&[][..], |obj| &obj.place[..]);
                (o, entries.iter().rev().find(|e| e.t <= reference + 1e-9).and_then(|e| e.p.clone()))
            })
            .collect();
        for (signal, src) in &sources {
            let timeline = &mut self.scene.signals[*signal as usize].timeline;
            timeline.push(Entry::Set { t, src: src.clone(), span: Span::default() });
            self.log.push(Op::Entry { signal: *signal, index: timeline.len() - 1 });
        }
        for (object, want) in present {
            if self.scene.present(object, t) != want {
                self.set_presence(object, t, want);
            }
        }
        for (object, p) in placed {
            self.insert_place(object, PlaceEntry { t, dur: 0.0, ease: Default::default(), p, span: Span::default() });
        }
        to_json(&sources.iter().map(|(s, src)| (s, src)).collect::<Vec<_>>())
    }

    /// The stretches of the timeline a video plays (a lesson: its correct path), as JSON.
    fn video_path(&self) -> String {
        to_json(&self.scene.video_path())
    }

    /// The scene's questions (`s.ask`), replacing any set before.
    fn set_questions(&mut self, questions_json: &str) -> PyResult<()> {
        self.scene.questions = parse::<Vec<Question>>("questions", questions_json)?;
        Ok(())
    }
}
