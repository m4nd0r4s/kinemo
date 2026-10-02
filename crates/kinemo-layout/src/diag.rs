//! Problems detected while resolving layout.

use kinemo_ir::ObjectId;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LayoutIssueKind {
    /// Constraints depend on each other in a loop (K0402).
    Cycle,
    /// Two constraints fight over the same axis (K0403).
    Contradiction,
}

#[derive(Clone, Debug, PartialEq)]
pub struct LayoutIssue {
    pub kind: LayoutIssueKind,
    pub objects: Vec<ObjectId>,
    pub t: f64,
}
