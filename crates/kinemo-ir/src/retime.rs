//! Log of timed IR insertions, so a block of the timeline can be re-timed afterwards
//! (progressive `s.tempo(1, to=8)`, whose length is only known at the end of the block).

use crate::{Entry, ObjectId, Scene, SignalId};

/// A timed insertion into the scene, by position.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Op {
    Entry { signal: SignalId, index: usize },
    Presence { object: ObjectId, index: usize },
    Place { object: ObjectId, index: usize },
    Mark { index: usize },
    Audio { index: usize },
}

/// Time warp of a block starting at `t0` whose local length is `len`, with speed going
/// linearly from `f0` to `f1`. Times after the block keep the final speed.
#[derive(Clone, Copy, Debug)]
pub struct Warp {
    pub t0: f64,
    pub len: f64,
    pub f0: f64,
    pub f1: f64,
}

impl Warp {
    fn integral(&self, u: f64) -> f64 {
        if (self.f1 - self.f0).abs() < 1e-12 || self.len <= 0.0 {
            return u / self.f0;
        }
        let k = (self.f1 - self.f0) / self.len;
        ((self.f0 + k * u) / self.f0).ln() / k
    }

    pub fn apply(&self, t: f64) -> f64 {
        let u = t - self.t0;
        if u <= 0.0 {
            t
        } else if u <= self.len {
            self.t0 + self.integral(u)
        } else {
            self.t0 + self.integral(self.len) + (u - self.len) / self.f1
        }
    }
}

pub fn remap(scene: &mut Scene, ops: &[Op], w: Warp) {
    for op in ops {
        match *op {
            Op::Entry { signal, index } => match &mut scene.signals[signal as usize].timeline[index] {
                Entry::Set { t, .. } => *t = w.apply(*t),
                Entry::Anim { t0, t1, .. } => {
                    *t0 = w.apply(*t0);
                    *t1 = w.apply(*t1);
                }
            },
            Op::Presence { object, index } => {
                let p = &mut scene.objects[object as usize].presence[index];
                p.0 = w.apply(p.0);
            }
            Op::Place { object, index } => {
                let e = &mut scene.objects[object as usize].place[index];
                let end = w.apply(e.t + e.dur);
                e.t = w.apply(e.t);
                e.dur = end - e.t;
            }
            Op::Mark { index } => scene.marks[index].t = w.apply(scene.marks[index].t),
            Op::Audio { index } => scene.audio[index].t = w.apply(scene.audio[index].t),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn constant_speed_divides() {
        let w = Warp { t0: 1.0, len: 4.0, f0: 2.0, f1: 2.0 };
        assert!((w.apply(5.0) - 3.0).abs() < 1e-12);
    }

    #[test]
    fn accelerating_block_is_shorter_than_start_speed() {
        let w = Warp { t0: 0.0, len: 10.0, f0: 1.0, f1: 4.0 };
        let end = w.apply(10.0);
        assert!(end < 10.0 && end > 2.5);
        assert!(w.apply(5.0) > end / 2.0);
    }
}
