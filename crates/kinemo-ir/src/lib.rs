//! kinemo IR: the serializable scene graph produced by the Python build phase.
//!
//! Everything below the IR (evaluation, layout, rendering) consumes only these types,
//! so every crate except `kinemo-py` can be tested from a JSON scene.

mod expr;
mod object;
mod placement;
pub mod retime;
mod scene;
mod span;
mod timeline;
mod value;

pub use expr::{BinOp, Expr, UnOp};
pub use object::Object;
pub use placement::{PlaceEntry, Placement, Side};
pub use scene::{Audio, Mark, Scene, SceneConfig, Table};
pub use span::Span;
pub use timeline::{Blend, Ease, Entry, Lerp, Signal, Src};
pub use value::Value;

pub const IR_VERSION: &str = "1.0.0";

pub type SignalId = u32;
pub type ObjectId = u32;
