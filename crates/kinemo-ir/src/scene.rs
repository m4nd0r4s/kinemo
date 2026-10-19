//! The scene: configuration, all nodes and resolve-phase tables.

use serde::{Deserialize, Serialize};

use crate::{Object, ObjectId, Question, Signal, SignalId, IR_VERSION};


#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Mark {
    #[serde(default)]
    pub name: Option<String>,
    pub t: f64,
    #[serde(default)]
    pub slide: bool,
}

/// A sampled table on a uniform time grid (resolve-phase output).
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Table {
    pub t0: f64,
    pub dt: f64,
    pub values: Vec<f64>,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct SceneConfig {
    pub name: String,
    pub width: u32,
    pub height: u32,
    pub fps: f64,
    pub seed: u64,
    pub tail: f64,
    pub background: [f64; 4],
    /// Frame size in scene units (16 x 9 by default; 9 on the short side).
    pub frame_w: f64,
    pub frame_h: f64,
    /// Integrated loudness of the audio track in LUFS (`[audio] loudness`), or as mixed.
    #[serde(default)]
    pub loudness: Option<f64>,
    /// (top, right, bottom, left) of the frame covered by the app a vertical video is made for
    /// (`platform="reels"`), in scene units: the safe area stays clear of it.
    #[serde(default)]
    pub covered: [f64; 4],
}

impl Default for SceneConfig {
    fn default() -> Self {
        SceneConfig {
            name: "scene".into(),
            width: 1920,
            height: 1080,
            fps: 60.0,
            seed: 0,
            tail: 0.5,
            background: [0.07, 0.07, 0.09, 1.0],
            frame_w: 16.0,
            frame_h: 9.0,
            loudness: None,
            covered: [0.0; 4],
        }
    }
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Audio {
    pub path: String,
    pub t: f64,
    #[serde(default = "one")]
    pub gain: f64,
    /// What the clip is in the mix: narration, a sound effect, or background music.
    #[serde(default)]
    pub role: AudioRole,
    /// Music only: its level under the voice (0.25 = a quarter), 0 = no ducking.
    #[serde(default)]
    pub duck: f64,
    /// Music only: fade in at its start and out at the end of the scene, in seconds.
    #[serde(default)]
    pub fade: f64,
}

#[derive(Serialize, Deserialize, Clone, Copy, Debug, Default, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum AudioRole {
    Voice,
    #[default]
    Sound,
    Music,
}

fn one() -> f64 {
    1.0
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Default)]
pub struct Scene {
    pub ir_version: String,
    pub config: SceneConfig,
    pub duration: f64,
    pub signals: Vec<Signal>,
    pub objects: Vec<Object>,
    #[serde(default)]
    pub marks: Vec<Mark>,
    #[serde(default)]
    pub tables: Vec<Table>,
    #[serde(default)]
    pub audio: Vec<Audio>,
    /// Ids of root objects in insertion order (draw order tie-breaker).
    #[serde(default)]
    pub roots: Vec<ObjectId>,
    /// Questions of an interactive lesson (`s.ask`), in timeline order.
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub questions: Vec<Question>,
}


impl Scene {
    pub fn new(config: SceneConfig) -> Self {
        Scene {
            ir_version: IR_VERSION.into(),
            config,
            ..Default::default()
        }
    }

    pub fn to_json(&self) -> String {
        serde_json::to_string(self).expect("IR serializes")
    }

    pub fn from_json(s: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(s)
    }

    pub fn object(&self, id: ObjectId) -> &Object {
        &self.objects[id as usize]
    }

    pub fn signal(&self, id: SignalId) -> &Signal {
        &self.signals[id as usize]
    }

    pub fn prop(&self, obj: ObjectId, name: &str) -> Option<SignalId> {
        self.objects[obj as usize].props.get(name).copied()
    }

    /// Whether the object itself is present at `t` (ancestors are not considered).
    /// The stretches of the timeline a video plays: everything except the wrong branches of a
    /// lesson's questions (the whole timeline when it has none).
    pub fn video_path(&self) -> Vec<(f64, f64)> {
        let mut path = Vec::new();
        let mut from = 0.0;
        for q in &self.questions {
            let pause = q.branches.iter().map(|b| b.t0).fold(q.resume, f64::min);
            path.push((from, pause));
            if let Some(correct) = q.branches.iter().find(|b| b.on == crate::Outcome::Correct) {
                path.push((correct.t0, correct.t1));
            }
            from = q.resume;
        }
        path.push((from, self.duration));
        path.retain(|(a, b)| b > a);
        path
    }

    /// The scene as a video shows it: each question's answer takes its correct value once the
    /// question is asked (the learner's answer, in the player).
    pub fn with_correct_answers(&self) -> Scene {
        let mut scene = self.clone();
        for q in &self.questions {
            let (Some(signal), Some(value)) = (q.signal, q.answer.correct_value()) else { continue };
            let pause = q.branches.iter().map(|b| b.t0).fold(q.resume, f64::min);
            let timeline = &mut scene.signals[signal as usize].timeline;
            timeline.push(crate::Entry::Set { t: pause, src: crate::Src::Val { v: value }, span: Default::default() });
        }
        scene
    }

    pub fn present(&self, obj: ObjectId, t: f64) -> bool {
        let mut state = false;
        for (pt, p) in &self.objects[obj as usize].presence {
            if *pt <= t {
                state = *p;
            } else {
                break;
            }
        }
        state
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::*;

    #[test]
    fn a_video_takes_the_correct_answer_when_the_question_is_asked() {
        let mut scene = Scene::new(SceneConfig::default());
        scene.signals.push(Signal { id: 0, initial: Value::Float(0.5), lerp: Lerp::Linear, timeline: vec![], owner: None, span: Span::default() });
        scene.questions.push(Question {
            id: "q1".into(),
            t: 2.0,
            prompt: "?".into(),
            answer: Answer::Number { lo: Some(0.0), hi: Some(4.0), step: None, correct: 2.0, tolerance: 0.1 },
            signal: Some(0),
            default: serde_json::json!(0.5),
            branches: vec![Branch { on: Outcome::Correct, t0: 2.1, t1: 3.0, then: Then::Continue, span: Span::default() }],
            resume: 3.0,
            span: Span::default(),
        });
        let video = scene.with_correct_answers();
        assert_eq!(video.signals[0].timeline, vec![Entry::Set { t: 2.1, src: Src::Val { v: Value::Float(2.0) }, span: Span::default() }]);
        assert!(scene.signals[0].timeline.is_empty(), "the player's scene keeps the learner's answer");
    }

    #[test]
    fn roundtrip_json() {
        let mut s = Scene::new(SceneConfig::default());
        s.signals.push(Signal {
            id: 0,
            initial: Value::Float(1.0),
            lerp: Lerp::Linear,
            timeline: vec![Entry::Anim {
                t0: 0.0,
                t1: 1.0,
                to: Src::Val { v: Value::Float(3.0) },
                from: None,
                ease: Ease::Smooth,
                blend: Blend::Replace,
                span: Span::default(),
            }],
            owner: None,
            span: Span::default(),
        });
        let j = s.to_json();
        let back = Scene::from_json(&j).unwrap();
        assert_eq!(s, back);
    }

    #[test]
    fn presence_toggles() {
        let mut s = Scene::new(SceneConfig::default());
        s.objects.push(Object {
            presence: vec![(1.0, true), (3.0, false)],
            ..Default::default()
        });
        assert!(!s.present(0, 0.5));
        assert!(s.present(0, 1.0));
        assert!(s.present(0, 2.9));
        assert!(!s.present(0, 3.0));
    }
}
