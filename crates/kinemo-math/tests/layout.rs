//! Public-API tests for kinemo-math.

use std::sync::Arc;
use std::time::Instant;

use kinemo_math::{
    find, glyphs_of, layout_math, layout_math_without_markers, named, rules_of, MathError, MathLayout, MathOptions,
};
use kurbo::Shape;

fn lay(tex: &str) -> Arc<MathLayout> {
    layout_math(tex, &MathOptions::default()).unwrap_or_else(|e| panic!("{tex}: {e}"))
}

fn approx(a: f64, b: f64) -> bool {
    (a - b).abs() < 1e-9
}

/// Ink bounding box of all glyphs and rules.
fn ink_box(l: &MathLayout) -> kurbo::Rect {
    let mut boxes = l.glyphs.iter().map(|g| g.path.bounding_box()).chain(l.rules.iter().map(|r| r.0.bounding_box()));
    let first = boxes.next().expect("some ink");
    boxes.fold(first, |a, b| a.union(b))
}

#[test]
fn basic_formulas_lay_out() {
    let cases: &[(&str, usize, usize)] = &[
        // (tex, min glyphs, min rules)
        ("a^2 + b^2 = c^2", 8, 0),
        (r"\frac{a}{b}", 2, 1),
        (r"\sqrt{x}", 2, 1),
        (r"\sum_{i=1}^n i", 6, 0),
        (r"\int_0^1 x\,dx", 6, 0),
        (r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}", 6, 0),
        (r"\begin{bmatrix} 1 & 0 \\ 0 & 1 \end{bmatrix}", 6, 0),
        (r"|x| = \begin{cases} x & x \geq 0 \\ -x & x < 0 \end{cases}", 12, 0),
        (r"\lim_{x \to 0} \frac{\sin x}{x} = 1", 12, 1),
        (r"\boxed{E = mc^2}", 4, 1),
    ];
    for &(tex, min_glyphs, min_rules) in cases {
        let l = lay(tex);
        assert!(l.glyphs.len() >= min_glyphs, "{tex}: {} glyphs", l.glyphs.len());
        assert!(l.rules.len() >= min_rules, "{tex}: {} rules", l.rules.len());
        for g in &l.glyphs {
            assert!(!g.path.elements().is_empty(), "{tex}: empty glyph");
            assert!(g.node < l.parts.len());
        }
        // Strokes (the `\boxed` frame) may overhang the logical box by half their width.
        let ink = ink_box(&l);
        assert!(l.bbox.inflate(0.02, 0.02).contains_rect(ink), "{tex}: ink {ink:?} outside bbox {:?}", l.bbox);
    }
}

#[test]
fn bbox_is_centered_and_scales_with_size() {
    let small = lay(r"\frac{a+b}{c}");
    assert!(approx(small.bbox.center().x, 0.0) && approx(small.bbox.center().y, 0.0));
    let big = layout_math(r"\frac{a+b}{c}", &MathOptions { size: 1.0, display: true }).unwrap();
    assert!(approx(big.bbox.width(), 2.0 * small.bbox.width()));
    assert!(approx(big.bbox.height(), 2.0 * small.bbox.height()));
    // y-up: the numerator is above the denominator.
    let a = find(&small, "a+b")[0];
    let c = find(&small, "c")[0];
    let y_of = |n: usize| small.glyphs[glyphs_of(&small, n)[0]].path.bounding_box().center().y;
    assert!(y_of(a) > y_of(c));
}

#[test]
fn inline_style_is_smaller_than_display() {
    let display = lay(r"\sum_{i=1}^n \frac{1}{i}");
    let inline = layout_math(r"\sum_{i=1}^n \frac{1}{i}", &MathOptions { display: false, ..Default::default() }).unwrap();
    assert!(inline.bbox.height() < display.bbox.height());
    assert!(approx(inline.bbox.center().y, 0.0));
}

#[test]
fn id_parts_and_tex_search() {
    let l = lay(r"\id{lhs}{a^2 + b^2} = c^2");
    let lhs = named(&l, "lhs").expect("named part");
    assert_eq!(l.parts[lhs].tex, "a^{2}+b^{2}");
    assert_eq!(glyphs_of(&l, lhs).len(), 5, "a 2 + b 2");
    assert_eq!(named(&l, "rhs"), None);

    let c2 = find(&l, "c^2");
    assert_eq!(c2.len(), 1);
    assert_eq!(c2, find(&l, "c^{2}"));
    assert_eq!(c2, find(&l, "{c}^{ 2 }"));
    assert_eq!(glyphs_of(&l, c2[0]).len(), 2);
    assert_eq!(find(&l, "a^{2}+b^{2}"), vec![lhs]);
    assert!(find(&l, "d^2").is_empty());
    assert_eq!(glyphs_of(&l, 0).len(), l.glyphs.len(), "root holds everything");

    // Repeated subexpressions are all found, in order.
    let l = lay(r"x^2 + \frac{x^2}{2}");
    let xs = find(&l, "x^2");
    assert_eq!(xs.len(), 2);
    assert!(xs[0] < xs[1]);
}

#[test]
fn rules_belong_to_their_node() {
    let l = lay(r"1 + \frac{a}{b}");
    let frac = find(&l, r"\frac{a}{b}")[0];
    assert_eq!(rules_of(&l, frac).len(), 1, "the fraction bar");
    assert_eq!(glyphs_of(&l, frac).len(), 2);
    let l = lay(r"\sqrt{x+1}");
    let sqrt = find(&l, r"\sqrt{x+1}")[0];
    assert_eq!(rules_of(&l, sqrt).len(), 1, "the radical's overline");
    assert_eq!(glyphs_of(&l, sqrt).len(), 4, "radical sign + x + 1");
}

#[test]
fn errors() {
    let err = layout_math(r"\foobar{x}", &MathOptions::default()).unwrap_err();
    assert_eq!(err, MathError::Unsupported { command: r"\foobar".into() });
    assert_eq!(err.code(), Some("K0801"));
    assert!(err.to_string().contains("K0801"), "{err}");
    let err = layout_math(r"\begin{tikzpicture}\end{tikzpicture}", &MathOptions::default()).unwrap_err();
    assert!(matches!(err, MathError::Unsupported { .. }), "{err:?}");
    assert!(matches!(layout_math(r"\frac{a}{b", &MathOptions::default()), Err(MathError::Syntax(_))));
    assert!(matches!(layout_math(r"\left( x", &MathOptions::default()), Err(MathError::Syntax(_))));
    assert!(matches!(layout_math(r"x^2^3", &MathOptions::default()), Err(MathError::Syntax(_))));
}

#[test]
fn deterministic_and_cached() {
    let tex = r"\int_0^\infty e^{-x^2}\,dx = \frac{\sqrt{\pi}}{2}";
    let a = lay(tex);
    assert!(Arc::ptr_eq(&a, &lay(tex)), "cache hit");
    let b = layout_math_without_markers(tex, &MathOptions::default()).unwrap();
    let c = layout_math_without_markers(tex, &MathOptions::default()).unwrap();
    assert_eq!(b.glyphs.len(), c.glyphs.len());
    for (g, h) in b.glyphs.iter().zip(&c.glyphs) {
        assert_eq!(g.path, h.path);
    }
    assert_eq!(b.bbox, c.bbox);
}

/// Markers (fill colors) must not move anything. Formulas avoid constructs where
/// the marked tree is intentionally more faithful than plain mitex (`{a+b}^2`).
#[test]
fn markers_do_not_move_glyphs() {
    let formulas = [
        "a^2 + b^2 = c^2",
        r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
        r"\sum_{i=1}^{n} i = \frac{n(n+1)}{2}",
        r"\lim_{x \to 0} \frac{\sin x}{x} = 1",
        r"\int_0^1 x^2\,dx = \frac{1}{3}",
        r"\begin{pmatrix} a & b \\ c & d \end{pmatrix} \begin{pmatrix} x \\ y \end{pmatrix}",
        r"\left( \frac{a}{b} \right)^2 - \sqrt[3]{x}",
        r"f'(x) = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h}",
        r"\nabla \times \mathbf{B} = \mu_0 \mathbf{J} + \mu_0 \varepsilon_0 \frac{\partial \mathbf{E}}{\partial t}",
        r"P(A \mid B) = \frac{P(B \mid A) P(A)}{P(B)}",
        r"\begin{aligned} f(x) &= (x+1)^2 \\ &= x^2 + 2x + 1 \end{aligned}",
        r"\operatorname{tr}(A) = \sum_{i} a_{ii}, \quad \hat{H}\Psi = E\Psi",
    ];
    let opts = MathOptions::default();
    let mut max_deviation: f64 = 0.0;
    for tex in formulas {
        let marked = layout_math(tex, &opts).unwrap();
        let plain = layout_math_without_markers(tex, &opts).unwrap();
        assert_eq!(marked.glyphs.len(), plain.glyphs.len(), "{tex}");
        assert_eq!(marked.rules.len(), plain.rules.len(), "{tex}");
        assert!((marked.bbox.width() - plain.bbox.width()).abs() < 1e-9, "{tex}");
        for (m, p) in marked.glyphs.iter().zip(&plain.glyphs) {
            let (a, b) = (m.path.bounding_box(), p.path.bounding_box());
            let d = (a.x0 - b.x0).abs().max((a.y0 - b.y0).abs()).max((a.x1 - b.x1).abs()).max((a.y1 - b.y1).abs());
            max_deviation = max_deviation.max(d);
        }
        assert!(plain.glyphs.iter().all(|g| g.node == 0), "unmarked ink belongs to the root");
    }
    println!("max glyph deviation with vs without markers: {max_deviation:e} scene units");
    assert!(max_deviation < 1e-9, "markers moved glyphs by {max_deviation}");
}

#[test]
fn timing_after_warmup() {
    let opts = MathOptions::default();
    let _ = layout_math("x", &opts);
    let formulas = [
        r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
        r"\int_{-\infty}^{\infty} e^{-x^2}\,dx = \sqrt{\pi}",
        r"\begin{pmatrix} \cos\theta & -\sin\theta \\ \sin\theta & \cos\theta \end{pmatrix}",
        r"i\hbar \frac{\partial}{\partial t} \Psi = \hat{H} \Psi",
        r"\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}",
    ];
    let mut worst: f64 = 0.0;
    for (i, tex) in formulas.iter().enumerate() {
        // A unique size defeats kinemo's cache; typst's memoization still applies
        // to the shared prelude, as it would in real use.
        let opts = MathOptions { size: 0.5 + i as f64 * 1e-6, display: true };
        let start = Instant::now();
        layout_math(tex, &opts).unwrap();
        let ms = start.elapsed().as_secs_f64() * 1000.0;
        println!("{ms:6.2} ms  {tex}");
        worst = worst.max(ms);
    }
    // Generous bound so debug builds pass; release numbers are ~1 ms.
    assert!(worst < if cfg!(debug_assertions) { 200.0 } else { 20.0 }, "worst {worst:.1} ms");
}
