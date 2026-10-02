//! Deterministic smooth 1D value noise (`k.noise`).

/// Smooth value noise at `x`: random values in `[-1, 1]` at integer lattice
/// points, blended with a quintic fade. Deterministic for a given `seed`;
/// the output always lies in `[-1, 1]`.
pub fn noise1(x: f64, seed: u32) -> f64 {
    if !x.is_finite() {
        return 0.0;
    }
    let i = x.floor();
    let f = x - i;
    let i = i as i64;
    let u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    let a = lattice(i, seed);
    let b = lattice(i.wrapping_add(1), seed);
    a + (b - a) * u
}

/// Hashes a lattice coordinate to a value in `[-1, 1]` (splitmix64 finalizer).
fn lattice(i: i64, seed: u32) -> f64 {
    let mut z = (i as u64) ^ (u64::from(seed) << 32 | u64::from(seed)).wrapping_mul(0x9E37_79B9_7F4A_7C15);
    z = z.wrapping_add(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^= z >> 31;
    (z >> 11) as f64 / (1u64 << 53) as f64 * 2.0 - 1.0
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounded_and_deterministic() {
        for i in -500..500 {
            let x = i as f64 * 0.137;
            let v = noise1(x, 7);
            assert!((-1.0..=1.0).contains(&v));
            assert_eq!(v, noise1(x, 7));
        }
    }

    #[test]
    fn seed_changes_output() {
        let differs = (0..20).any(|i| noise1(i as f64 + 0.5, 1) != noise1(i as f64 + 0.5, 2));
        assert!(differs);
    }

    #[test]
    fn continuous() {
        let mut prev = noise1(0.0, 3);
        for i in 1..10_000 {
            let v = noise1(i as f64 * 0.001, 3);
            assert!((v - prev).abs() < 0.01);
            prev = v;
        }
    }

    #[test]
    fn varies() {
        let vals: Vec<f64> = (0..50).map(|i| noise1(i as f64 * 0.7, 0)).collect();
        let spread = vals.iter().cloned().fold(f64::MIN, f64::max) - vals.iter().cloned().fold(f64::MAX, f64::min);
        assert!(spread > 0.5);
        assert!(noise1(f64::NAN, 0) == 0.0);
    }
}
