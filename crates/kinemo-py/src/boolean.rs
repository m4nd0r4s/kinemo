//! Boolean shape operations (`k.union`, `k.intersect`, `k.subtract`) on world outlines.

use i_overlay::core::fill_rule::FillRule;
use i_overlay::core::overlay_rule::OverlayRule;
use i_overlay::float::single::SingleFloatOverlay;
use kurbo::{BezPath, PathEl, Point};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use crate::builder::Builder;

type Contour = Vec<[f64; 2]>;

fn contours_of(path: &BezPath) -> Vec<Contour> {
    let mut out: Vec<Contour> = Vec::new();
    kurbo::flatten(path, 1e-3, |el| match el {
        PathEl::MoveTo(p) => out.push(vec![[p.x, p.y]]),
        PathEl::LineTo(p) => {
            if let Some(c) = out.last_mut() {
                c.push([p.x, p.y]);
            }
        }
        _ => {}
    });
    out.into_iter().filter(|c| c.len() > 2).collect()
}

fn rule(name: &str) -> PyResult<OverlayRule> {
    match name {
        "union" => Ok(OverlayRule::Union),
        "intersect" => Ok(OverlayRule::Intersect),
        "subtract" => Ok(OverlayRule::Difference),
        "xor" => Ok(OverlayRule::Xor),
        other => Err(PyValueError::new_err(format!("unknown boolean operation '{other}'"))),
    }
}

/// SVG path data of the closed contours, in world coordinates.
fn to_svg(shapes: &[Vec<Contour>]) -> String {
    let mut path = BezPath::new();
    for contour in shapes.iter().flatten() {
        for (i, [x, y]) in contour.iter().enumerate() {
            let p = Point::new(*x, *y);
            if i == 0 {
                path.move_to(p);
            } else {
                path.line_to(p);
            }
        }
        path.close_path();
    }
    path.to_svg()
}

#[pymethods]
impl Builder {
    /// Result of a boolean operation between the world outlines of two objects at `t`.
    fn boolean_path(&self, operation: &str, a: u32, b: u32, t: f64) -> PyResult<String> {
        let op = rule(operation)?;
        let outline = |o: u32| -> Vec<Contour> {
            self.with_layout(|l| {
                let mut all = Vec::new();
                let mut stack = vec![o];
                while let Some(n) = stack.pop() {
                    if l.scene().object(n).children.is_some() {
                        stack.extend(l.children(n, t));
                    } else {
                        let affine = l.world_affine(n, t);
                        for part in l.parts(n, t) {
                            all.extend(contours_of(&(affine * part.path)));
                        }
                    }
                }
                all
            })
        };
        let (subject, clip) = (outline(a), outline(b));
        let shapes = subject.overlay(&clip, op, FillRule::NonZero);
        Ok(to_svg(&shapes))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn union_of_overlapping_squares() {
        let a: Vec<Contour> = vec![vec![[0.0, 0.0], [2.0, 0.0], [2.0, 2.0], [0.0, 2.0]]];
        let b: Vec<Contour> = vec![vec![[1.0, 1.0], [3.0, 1.0], [3.0, 3.0], [1.0, 3.0]]];
        let shapes = a.overlay(&b, OverlayRule::Union, FillRule::NonZero);
        assert_eq!(shapes.len(), 1);
        assert!(to_svg(&shapes).starts_with('M'));
    }
}
