//! Path geometry helpers: measurement, trimming and resampling.

mod measure;
mod resample;
mod trim;

pub use measure::{bbox, path_length};
pub use resample::resample_points;
pub use trim::trim;

/// Absolute accuracy used for arc-length computations (pixels / scene units).
pub(crate) const ARCLEN_ACCURACY: f64 = 1e-4;

#[cfg(test)]
mod tests;
