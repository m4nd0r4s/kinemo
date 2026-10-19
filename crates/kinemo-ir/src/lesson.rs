//! Questions of an interactive lesson (`s.ask`).
//!
//! A lesson is still one timeline: a question is an instant where playback stops, and each of
//! its branches is a stretch of that timeline laid after it. Every branch starts from the state
//! at the question and the lesson resumes from the state at the end of the correct branch, so a
//! frame stays a pure function of time; the player only decides which stretch plays next.

use serde::{Deserialize, Serialize};

use crate::{SignalId, Span};

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Question {
    /// Stable id for the host platform (`name=`, else `q1`, `q2`...).
    pub id: String,
    /// Where playback stops to ask.
    pub t: f64,
    pub prompt: String,
    pub answer: Answer,
    /// The signal holding the learner's answer, when the scene uses it (the player sets it).
    #[serde(default)]
    pub signal: Option<SignalId>,
    /// The answer before the learner gives one, in the terms of [`Answer::grade`] (an option
    /// index, a number, a point or a text): where a slider or a dragged point starts.
    #[serde(default)]
    pub default: serde_json::Value,
    #[serde(default)]
    pub branches: Vec<Branch>,
    /// Where the lesson continues after a correct answer (and its branch).
    pub resume: f64,
    #[serde(default)]
    pub span: Span,
}

/// What the learner answers with, and what counts as correct.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum Answer {
    /// Pick one option; `correct` holds the indices that count.
    Choice { options: Vec<String>, correct: Vec<usize> },
    /// A number: a slider over `[lo, hi]` in steps of `step`, or a field when there is no range.
    Number {
        #[serde(default)]
        lo: Option<f64>,
        #[serde(default)]
        hi: Option<f64>,
        #[serde(default)]
        step: Option<f64>,
        correct: f64,
        #[serde(default)]
        tolerance: f64,
    },
    /// Drag a point (in scene units) to within `tolerance` of `correct`.
    Point {
        correct: [f64; 2],
        #[serde(default)]
        tolerance: f64,
    },
    /// Type a short text; compared without case or surrounding spaces.
    Text { correct: Vec<String> },
}

#[derive(Serialize, Deserialize, Clone, Copy, Debug, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Outcome {
    Correct,
    Wrong,
}

/// What follows a branch once it has played.
#[derive(Serialize, Deserialize, Clone, Copy, Debug, PartialEq, Eq, Default)]
#[serde(rename_all = "snake_case")]
pub enum Then {
    /// Back to the question, to answer again.
    #[default]
    Retry,
    /// On with the lesson, from [`Question::resume`].
    Continue,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Branch {
    pub on: Outcome,
    pub t0: f64,
    pub t1: f64,
    #[serde(default)]
    pub then: Then,
    #[serde(default)]
    pub span: Span,
}

impl Answer {
    /// Whether `value` (an option index, a number, a point or a text) is correct.
    pub fn grade(&self, value: &serde_json::Value) -> bool {
        match self {
            Answer::Choice { correct, .. } => value.as_u64().is_some_and(|i| correct.contains(&(i as usize))),
            Answer::Number { correct, tolerance, .. } => value.as_f64().is_some_and(|v| (v - correct).abs() <= tolerance + 1e-9),
            Answer::Point { correct, tolerance, .. } => match value.as_array().map(|a| a.iter().filter_map(|x| x.as_f64()).collect::<Vec<_>>()) {
                Some(p) if p.len() == 2 => (p[0] - correct[0]).hypot(p[1] - correct[1]) <= tolerance + 1e-9,
                _ => false,
            },
            Answer::Text { correct } => value.as_str().is_some_and(|v| correct.iter().any(|c| c.trim().eq_ignore_ascii_case(v.trim()))),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn answers_grade_their_kind_of_value() {
        let choice = Answer::Choice { options: vec!["1".into(), "2".into(), "4".into()], correct: vec![2] };
        assert!(choice.grade(&json!(2)) && !choice.grade(&json!(1)) && !choice.grade(&json!("4")));
        let number = Answer::Number { lo: None, hi: None, step: None, correct: 4.0, tolerance: 0.1 };
        assert!(number.grade(&json!(4.1)) && !number.grade(&json!(4.2)));
        let point = Answer::Point { correct: [1.0, 2.0], tolerance: 0.5 };
        assert!(point.grade(&json!([1.3, 2.3])) && !point.grade(&json!([2.0, 2.0])));
        let text = Answer::Text { correct: vec!["Slope".into()] };
        assert!(text.grade(&json!("  slope ")) && !text.grade(&json!("rate")));
    }

    #[test]
    fn a_question_round_trips_through_json() {
        let q = Question {
            id: "q1".into(),
            t: 2.0,
            prompt: "What is the slope at x = 2?".into(),
            answer: Answer::Choice { options: vec!["1".into(), "4".into()], correct: vec![1] },
            signal: None,
            default: serde_json::json!(0),
            branches: vec![Branch { on: Outcome::Wrong, t0: 2.1, t1: 4.0, then: Then::Retry, span: Span::default() }],
            resume: 6.0,
            span: Span::default(),
        };
        let text = serde_json::to_string(&q).unwrap();
        assert!(text.contains(r#""kind":"choice""#) && text.contains(r#""on":"wrong""#));
        assert_eq!(serde_json::from_str::<Question>(&text).unwrap(), q);
    }
}
