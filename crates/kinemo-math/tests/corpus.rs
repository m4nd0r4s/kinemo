//! Corpus success rate: `tests/math_corpus/formulas.txt` at the workspace root.
//! Success = `layout_math` returns Ok with at least one glyph. Target ≥ 98%.
//! Run with `--nocapture` to see failures and timings.

use std::time::Instant;

use kinemo_math::{layout_math, MathOptions};

fn corpus() -> Vec<String> {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../../tests/math_corpus/formulas.txt");
    let text = std::fs::read_to_string(path).expect("corpus file");
    text.lines().map(str::trim).filter(|l| !l.is_empty() && !l.starts_with('#')).map(str::to_owned).collect()
}

#[test]
fn corpus_success_rate() {
    let formulas = corpus();
    assert!(formulas.len() >= 150, "corpus has {} formulas", formulas.len());
    let opts = MathOptions::default();
    // Warm up fonts, the typst library and the mitex spec.
    let _ = layout_math("x", &opts);

    let mut failures = Vec::new();
    let mut times = Vec::new();
    for f in &formulas {
        let start = Instant::now();
        let result = layout_math(f, &opts);
        times.push(start.elapsed().as_secs_f64() * 1000.0);
        match result {
            Ok(l) if !l.glyphs.is_empty() => {}
            Ok(_) => failures.push(format!("{f}  ->  no glyphs")),
            Err(e) => failures.push(format!("{f}  ->  {e}")),
        }
    }
    times.sort_by(f64::total_cmp);
    let rate = 1.0 - failures.len() as f64 / formulas.len() as f64;
    println!("corpus: {}/{} ok ({:.1}%)", formulas.len() - failures.len(), formulas.len(), rate * 100.0);
    println!(
        "first-layout time per formula: median {:.2} ms, p95 {:.2} ms, max {:.2} ms",
        times[times.len() / 2],
        times[times.len() * 95 / 100],
        times[times.len() - 1]
    );
    for f in &failures {
        println!("FAIL {f}");
    }
    assert!(rate >= 0.98, "success rate {:.1}% < 98%", rate * 100.0);
}

/// Markers must not move any glyph or rule anywhere in the corpus.
#[test]
fn corpus_markers_do_not_move_ink() {
    use kurbo::Shape;
    let opts = MathOptions::default();
    let mut max_deviation: f64 = 0.0;
    for f in corpus() {
        let (Ok(marked), Ok(plain)) = (layout_math(&f, &opts), kinemo_math::layout_math_without_markers(&f, &opts)) else {
            continue;
        };
        assert_eq!(marked.glyphs.len(), plain.glyphs.len(), "{f}");
        assert_eq!(marked.rules.len(), plain.rules.len(), "{f}");
        let boxes = |l: &kinemo_math::MathLayout| -> Vec<kurbo::Rect> {
            l.glyphs.iter().map(|g| g.path.bounding_box()).chain(l.rules.iter().map(|r| r.0.bounding_box())).collect()
        };
        for (a, b) in boxes(&marked).iter().zip(boxes(&plain).iter()) {
            let d = (a.x0 - b.x0).abs().max((a.y0 - b.y0).abs()).max((a.x1 - b.x1).abs()).max((a.y1 - b.y1).abs());
            max_deviation = max_deviation.max(d);
        }
    }
    println!("corpus max ink deviation with vs without markers: {max_deviation:e} scene units");
    assert!(max_deviation < 1e-9);
}
