//! Where a frame's time goes, for one scene IR.
//!
//! cargo run --release -p kinemo-render --example stage_timings -- scene.json [frames]
//!
//! `scene.json` comes from `scene.builder.to_json()`. Reports, per frame on one thread, the
//! display list (evaluation, layout, draw items) and rasterization; the fixed cost of a frame
//! (an empty list); and the throughput on every core.

use std::time::Instant;

use kinemo_ir::Scene;
use kinemo_render::raster::{rasterize, DisplayList};
use kinemo_eval::{Evaluator, TimelineIndex};
use kinemo_layout::Layout;
use kinemo_render::{display_list_with, FrameSize};
use std::sync::Arc;
use rayon::prelude::*;

fn main() {
    let mut args = std::env::args().skip(1);
    let path = args.next().expect("usage: stage_timings scene.json [frames]");
    let frames: usize = args.next().map(|n| n.parse().expect("frames is a number")).unwrap_or(120);
    let scene: Scene = serde_json::from_str(&std::fs::read_to_string(&path).expect("read scene")).expect("scene JSON");
    let size = FrameSize { width: 1920, height: 1080 };
    let duration = scene.duration.max(0.1);
    let time_of = |index: usize| duration * index as f64 / frames as f64;

    // As the renderer does: one timeline index per render, one evaluator per thread.
    let timeline = Arc::new(TimelineIndex::new(&scene));
    let evaluator = Evaluator::with_index(&scene, timeline.clone());
    let (mut building, mut rasterizing, mut items) = (0.0, 0.0, 0usize);
    for index in 0..frames {
        let start = Instant::now();
        evaluator.clear();
        let list = display_list_with(&Layout::new(&evaluator), time_of(index), size, false);
        let built = Instant::now();
        std::hint::black_box(rasterize(&list, true));
        rasterizing += built.elapsed().as_secs_f64();
        building += (built - start).as_secs_f64();
        items += list.items.len();
    }

    let empty = DisplayList { width: size.width, height: size.height, background: scene.config.background, items: Vec::new() };
    let start = Instant::now();
    for _ in 0..frames {
        std::hint::black_box(rasterize(&empty, true));
    }
    let fixed = start.elapsed().as_secs_f64();

    let start = Instant::now();
    (0..frames).into_par_iter().for_each_init(
        || Evaluator::with_index(&scene, timeline.clone()),
        |evaluator, index| {
            evaluator.clear();
            std::hint::black_box(rasterize(&display_list_with(&Layout::new(evaluator), time_of(index), size, false), true));
        },
    );
    let parallel = start.elapsed().as_secs_f64();

    let per_frame = |seconds: f64| seconds * 1000.0 / frames as f64;
    println!("{path}");
    println!("  display list {:.2} ms, rasterize {:.2} ms per frame ({} items)", per_frame(building), per_frame(rasterizing), items / frames);
    println!("  fixed cost (empty frame) {:.2} ms", per_frame(fixed));
    println!("  {:.0} fps on {} threads, {:.0} fps on one", frames as f64 / parallel, rayon::current_num_threads(), frames as f64 / (building + rasterizing));
}
