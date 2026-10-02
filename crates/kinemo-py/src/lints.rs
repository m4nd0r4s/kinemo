//! Visual lints (W10xx) for `kinemo check`, computed by `kinemo-resolve`.

use pyo3::prelude::*;

use kinemo_resolve::{run_visual_lints, LintOptions};

use crate::builder::Builder;
use crate::errors::to_json;

#[pymethods]
impl Builder {
    /// Visual lints of the finished scene, sampling every `step` seconds (plus every
    /// timeline boundary). JSON list of findings: `code`, `objects`, `t`, `message`,
    /// `details` (tagged by `kind`), `fix` (tagged by `kind`, or null) and `span`.
    #[pyo3(signature = (step = 0.1))]
    fn visual_lints(&self, step: f64) -> String {
        to_json(&run_visual_lints(&self.scene, &LintOptions::with_step(step)))
    }
}
