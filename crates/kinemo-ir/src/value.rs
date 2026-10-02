//! Runtime values carried by signals and expressions.

use serde::{Deserialize, Serialize};

use crate::ObjectId;

/// A runtime value. Externally tagged so Python can build it unambiguously.
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq)]
pub enum Value {
    Float(f64),
    Int(i64),
    Bool(bool),
    Str(String),
    Vec2([f64; 2]),
    /// sRGB, straight alpha, components in 0..=1.
    Color([f64; 4]),
    List(Vec<Value>),
    Object(ObjectId),
    None,
}

impl Value {
    pub fn as_f64(&self) -> f64 {
        match self {
            Value::Float(v) => *v,
            Value::Int(v) => *v as f64,
            Value::Bool(b)
                if *b => {
                    1.0
                }
            _ => 0.0,
        }
    }
    pub fn as_bool(&self) -> bool {
        match self {
            Value::Bool(b) => *b,
            Value::Float(v) => *v != 0.0,
            Value::Int(v) => *v != 0,
            _ => false,
        }
    }
    pub fn as_v2(&self) -> [f64; 2] {
        match self {
            Value::Vec2(v) => *v,
            Value::Float(v) => [*v, *v],
            Value::Int(v) => [*v as f64, *v as f64],
            _ => [0.0, 0.0],
        }
    }
    pub fn as_color(&self) -> [f64; 4] {
        match self {
            Value::Color(c) => *c,
            _ => [0.0, 0.0, 0.0, 0.0],
        }
    }
    pub fn as_str(&self) -> String {
        match self {
            Value::Str(s) => s.clone(),
            Value::Float(v) => format!("{v}"),
            Value::Int(v) => format!("{v}"),
            Value::Bool(b) => format!("{b}"),
            _ => String::new(),
        }
    }
    pub fn as_list(&self) -> &[Value] {
        match self {
            Value::List(l) => l,
            _ => &[],
        }
    }
}
