//! Easing curves: maps animation progress `x ∈ [0, 1]` to eased progress.
//!
//! Every curve satisfies `apply(e, 0) == 0` and `apply(e, 1) == 1` (except a
//! user-provided [`Ease::Table`], which returns whatever its samples say).
//! `out_back`, `out_elastic` and `spring` may overshoot in between.

use kinemo_ir::Ease;
use std::f64::consts::PI;

/// Overshoot constant of the standard `out_back` curve.
const BACK_C1: f64 = 1.70158;

/// Fraction of the spring curve over which the residual error is blended out.
const SPRING_SETTLE: f64 = 0.1;

/// Evaluates easing `e` at progress `x` (clamped to `[0, 1]`; NaN maps to 0).
pub fn apply(e: &Ease, x: f64) -> f64 {
    let x = if x.is_nan() { 0.0 } else { x.clamp(0.0, 1.0) };
    match e {
        Ease::Linear => x,
        Ease::Smooth => cubic_in_out(x),
        Ease::In => x * x * x,
        Ease::Out => 1.0 - (1.0 - x).powi(3),
        Ease::InOut => -((PI * x).cos() - 1.0) / 2.0,
        Ease::OutBack => out_back(x),
        Ease::OutElastic => out_elastic(x),
        Ease::Spring { stiffness, damping } => spring(*stiffness, *damping, x),
        Ease::Steps { n } => steps(*n, x),
        Ease::Table { ys } => table(ys, x),
        Ease::Reverse { inner } => 1.0 - apply(inner, 1.0 - x),
    }
}

fn cubic_in_out(x: f64) -> f64 {
    if x < 0.5 {
        4.0 * x * x * x
    } else {
        1.0 - (-2.0 * x + 2.0).powi(3) / 2.0
    }
}

fn out_back(x: f64) -> f64 {
    let c3 = BACK_C1 + 1.0;
    let u = x - 1.0;
    1.0 + c3 * u.powi(3) + BACK_C1 * u.powi(2)
}

fn out_elastic(x: f64) -> f64 {
    if x <= 0.0 {
        return 0.0;
    }
    if x >= 1.0 {
        return 1.0;
    }
    let c4 = 2.0 * PI / 3.0;
    2f64.powf(-10.0 * x) * ((x * 10.0 - 0.75) * c4).sin() + 1.0
}

fn steps(n: u32, x: f64) -> f64 {
    if x >= 1.0 {
        return 1.0;
    }
    let n = f64::from(n.max(1));
    (x * n).floor() / n
}

/// Piecewise-linear curve through evenly spaced samples `ys` over `[0, 1]`.
pub(crate) fn table(ys: &[f64], x: f64) -> f64 {
    match ys.len() {
        0 => x,
        1 => ys[0],
        n => {
            let pos = x * (n - 1) as f64;
            let i = (pos.floor() as usize).min(n - 2);
            let f = pos - i as f64;
            ys[i] * (1.0 - f) + ys[i + 1] * f
        }
    }
}

/// Step response of a unit-mass damped oscillator `y'' = -k(y - 1) - c y'`,
/// with `y(0) = y'(0) = 0`, observed over unit time. The residual `1 - y(1)`
/// is blended in over the last 10% so the curve lands exactly on 1.
fn spring(stiffness: f64, damping: f64, x: f64) -> f64 {
    if stiffness.is_nan() || stiffness <= 0.0 {
        return x;
    }
    let raw = |tau: f64| spring_response(stiffness, damping.max(0.0), tau);
    let residual = 1.0 - raw(1.0);
    let w = ((x - (1.0 - SPRING_SETTLE)) / SPRING_SETTLE).clamp(0.0, 1.0);
    let w = w * w * (3.0 - 2.0 * w);
    if x >= 1.0 {
        1.0
    } else {
        raw(x) + residual * w
    }
}

fn spring_response(k: f64, c: f64, tau: f64) -> f64 {
    let w0 = k.sqrt();
    let zeta = c / (2.0 * w0);
    if (zeta - 1.0).abs() < 1e-9 {
        1.0 - (-w0 * tau).exp() * (1.0 + w0 * tau)
    } else if zeta < 1.0 {
        let wd = w0 * (1.0 - zeta * zeta).sqrt();
        let decay = (-zeta * w0 * tau).exp();
        1.0 - decay * ((wd * tau).cos() + (zeta * w0 / wd) * (wd * tau).sin())
    } else {
        let s = (zeta * zeta - 1.0).sqrt();
        let r1 = -w0 * (zeta - s);
        let r2 = -w0 * (zeta + s);
        1.0 + (r2 * (r1 * tau).exp() - r1 * (r2 * tau).exp()) / (r1 - r2)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn all() -> Vec<Ease> {
        vec![
            Ease::Linear,
            Ease::Smooth,
            Ease::In,
            Ease::Out,
            Ease::InOut,
            Ease::OutBack,
            Ease::OutElastic,
            Ease::Spring { stiffness: 100.0, damping: 10.0 },
            Ease::Spring { stiffness: 50.0, damping: 30.0 },
            Ease::Spring { stiffness: 25.0, damping: 10.0 },
            Ease::Steps { n: 4 },
            Ease::Table { ys: vec![0.0, 0.8, 1.0] },
            Ease::Reverse { inner: Box::new(Ease::In) },
        ]
    }

    fn close(a: f64, b: f64) -> bool {
        (a - b).abs() < 1e-9
    }

    #[test]
    fn endpoints() {
        for e in all() {
            assert!(close(apply(&e, 0.0), 0.0), "{e:?} at 0");
            assert!(close(apply(&e, 1.0), 1.0), "{e:?} at 1");
        }
    }

    #[test]
    fn clamps_input() {
        for e in all() {
            assert_eq!(apply(&e, -3.0), apply(&e, 0.0));
            assert_eq!(apply(&e, 7.0), apply(&e, 1.0));
        }
        assert_eq!(apply(&Ease::Linear, f64::NAN), 0.0);
    }

    #[test]
    fn known_values() {
        assert!(close(apply(&Ease::Smooth, 0.25), 4.0 * 0.25f64.powi(3)));
        assert!(close(apply(&Ease::Smooth, 0.5), 0.5));
        assert!(close(apply(&Ease::Smooth, 0.75), 1.0 - 0.5f64.powi(3) / 2.0));
        assert!(close(apply(&Ease::In, 0.5), 0.125));
        assert!(close(apply(&Ease::Out, 0.5), 0.875));
        assert!(close(apply(&Ease::InOut, 0.5), 0.5));
        assert!(close(apply(&Ease::Linear, 0.3), 0.3));
    }

    #[test]
    fn smooth_is_symmetric_and_monotonic() {
        let mut prev = 0.0;
        for i in 1..=100 {
            let x = i as f64 / 100.0;
            let y = apply(&Ease::Smooth, x);
            assert!(y >= prev);
            assert!(close(y, 1.0 - apply(&Ease::Smooth, 1.0 - x)));
            prev = y;
        }
    }

    #[test]
    fn overshooting_curves() {
        let max = |e: &Ease| (0..=1000).map(|i| apply(e, i as f64 / 1000.0)).fold(f64::MIN, f64::max);
        assert!(max(&Ease::OutBack) > 1.05);
        assert!(max(&Ease::OutElastic) > 1.1);
        assert!(max(&Ease::Spring { stiffness: 100.0, damping: 5.0 }) > 1.1);
        // Overdamped spring never overshoots.
        assert!(max(&Ease::Spring { stiffness: 50.0, damping: 30.0 }) <= 1.0 + 1e-12);
    }

    #[test]
    fn spring_is_continuous_near_end() {
        let e = Ease::Spring { stiffness: 4.0, damping: 1.0 }; // far from settled at x=1
        let a = apply(&e, 0.999_999);
        assert!((a - 1.0).abs() < 1e-3, "{a}");
        let mut prev = apply(&e, 0.0);
        for i in 1..=1000 {
            let y = apply(&e, i as f64 / 1000.0);
            assert!((y - prev).abs() < 0.05);
            prev = y;
        }
    }

    #[test]
    fn spring_degenerate_params() {
        let e = Ease::Spring { stiffness: 0.0, damping: 1.0 };
        assert!(close(apply(&e, 0.4), 0.4));
        let crit = Ease::Spring { stiffness: 100.0, damping: 20.0 };
        assert!(apply(&crit, 0.5) > 0.9 && apply(&crit, 0.5) < 1.0);
    }

    #[test]
    fn steps_curve() {
        let e = Ease::Steps { n: 4 };
        assert_eq!(apply(&e, 0.2), 0.0);
        assert_eq!(apply(&e, 0.25), 0.25);
        assert_eq!(apply(&e, 0.99), 0.75);
        assert_eq!(apply(&e, 1.0), 1.0);
        assert_eq!(apply(&Ease::Steps { n: 0 }, 0.5), 0.0);
    }

    #[test]
    fn table_curve() {
        let e = Ease::Table { ys: vec![0.0, 0.8, 1.0] };
        assert!(close(apply(&e, 0.25), 0.4));
        assert!(close(apply(&e, 0.5), 0.8));
        assert!(close(apply(&e, 0.75), 0.9));
        assert!(close(apply(&Ease::Table { ys: vec![] }, 0.3), 0.3));
        assert!(close(apply(&Ease::Table { ys: vec![0.5] }, 0.3), 0.5));
    }

    #[test]
    fn reverse_curve() {
        let e = Ease::Reverse { inner: Box::new(Ease::In) };
        assert!(close(apply(&e, 0.5), apply(&Ease::Out, 0.5)));
    }
}
