//! Typed reads of object props, with defaults for props the IR did not declare.

use kinemo_eval::Evaluated;
use kinemo_ir::{ObjectId, Value};

use crate::Layout;

impl<'a> Layout<'a> {
    /// Raw prop value at `t`, or `None` when the object has no such prop.
    pub fn prop(&self, obj: ObjectId, name: &str, t: f64) -> Option<Value> {
        let id = self.scene().prop(obj, name)?;
        match self.ev.signal(id, t, self) {
            Value::None => None,
            v => Some(v),
        }
    }

    pub fn prop_f(&self, obj: ObjectId, name: &str, t: f64, default: f64) -> f64 {
        self.prop(obj, name, t).map_or(default, |v| v.as_f64())
    }

    pub fn prop_v2(&self, obj: ObjectId, name: &str, t: f64, default: [f64; 2]) -> [f64; 2] {
        self.prop(obj, name, t).map_or(default, |v| v.as_v2())
    }

    pub fn prop_color(&self, obj: ObjectId, name: &str, t: f64) -> Option<[f64; 4]> {
        match self.prop(obj, name, t)? {
            Value::Color(c) => Some(c),
            _ => None,
        }
    }

    pub fn prop_bool(&self, obj: ObjectId, name: &str, t: f64, default: bool) -> bool {
        self.prop(obj, name, t).map_or(default, |v| v.as_bool())
    }

    pub fn prop_str(&self, obj: ObjectId, name: &str, t: f64) -> Option<String> {
        self.prop(obj, name, t).map(|v| v.as_str())
    }

    pub fn prop_points(&self, obj: ObjectId, name: &str, t: f64) -> Vec<kurbo::Point> {
        self.prop(obj, name, t)
            .map(|v| {
                v.as_list()
                    .iter()
                    .map(|p| {
                        let [x, y] = p.as_v2();
                        kurbo::Point::new(x, y)
                    })
                    .collect()
            })
            .unwrap_or_default()
    }

    /// Children of a group at `t`. During a reorder transition, returns the target order.
    pub fn children(&self, obj: ObjectId, t: f64) -> Vec<ObjectId> {
        match self.children_raw(obj, t) {
            Evaluated::Value(v) => obj_list(&v),
            Evaluated::Transition { to, .. } => obj_list(&to),
        }
    }

    pub(crate) fn children_raw(&self, obj: ObjectId, t: f64) -> Evaluated {
        match self.scene().object(obj).children {
            Some(id) => self.ev.signal_raw(id, t, self),
            None => Evaluated::Value(Value::List(vec![])),
        }
    }
}

pub(crate) fn obj_list(v: &Value) -> Vec<ObjectId> {
    v.as_list()
        .iter()
        .filter_map(|c| match c {
            Value::Object(id) => Some(*id),
            _ => None,
        })
        .collect()
}
