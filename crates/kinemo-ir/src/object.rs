//! Scene-graph nodes.

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

use crate::{ObjectId, PlaceEntry, SignalId, Span};


#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub struct Object {
    pub id: ObjectId,
    /// Shape/text/container kind: "circle", "rect", "text", "group", "row", ...
    pub kind: String,
    #[serde(default)]
    pub name: Option<String>,
    #[serde(default)]
    pub parent: Option<ObjectId>,
    /// Signal holding `Value::List(Value::Object..)` for groups and containers.
    #[serde(default)]
    pub children: Option<SignalId>,
    #[serde(default)]
    pub props: BTreeMap<String, SignalId>,
    #[serde(default)]
    pub place: Vec<PlaceEntry>,
    /// Presence toggles (time, present), sorted by time.
    #[serde(default)]
    pub presence: Vec<(f64, bool)>,
    #[serde(default)]
    pub span: Span,
}

impl Default for Object {
    fn default() -> Self {
        Object {
            id: 0,
            kind: "group".into(),
            name: None,
            parent: None,
            children: None,
            props: BTreeMap::new(),
            place: vec![],
            presence: vec![],
            span: Span::default(),
        }
    }
}
