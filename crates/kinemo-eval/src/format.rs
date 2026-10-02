//! A subset of Python's format-spec mini-language, used by `Expr::Format`
//! (`f"{x:.2f}"`) and for stringifying values in `Expr::Concat`.
//!
//! Grammar: `[[fill]align][sign][#][0][width][,|_][.precision][type]` with
//! `align ∈ {<, >, ^, =}`, `sign ∈ {+, -, space}` and
//! `type ∈ {f, F, d, e, E, g, G, %, s}` or absent.
//!
//! Deviations from Python (which would raise instead): `d` on a float rounds
//! it, `f`/`e`/`g`/`%` on a bool use 0/1, numbers accept `s`, and an
//! unparsable spec falls back to the plain string form of the value.

use kinemo_ir::Value;

#[derive(Debug, Clone, PartialEq)]
struct Spec {
    fill: char,
    align: Option<char>,
    sign: char,
    alternate: bool,
    width: usize,
    grouping: Option<char>,
    precision: Option<usize>,
    ty: Option<char>,
}

impl Default for Spec {
    fn default() -> Self {
        Spec { fill: ' ', align: None, sign: '-', alternate: false, width: 0, grouping: None, precision: None, ty: None }
    }
}

fn parse(spec: &str) -> Option<Spec> {
    let chars: Vec<char> = spec.chars().collect();
    let mut s = Spec::default();
    let mut i = 0;
    let is_align = |c: char| matches!(c, '<' | '>' | '^' | '=');

    if chars.len() >= 2 && is_align(chars[1]) {
        s.fill = chars[0];
        s.align = Some(chars[1]);
        i = 2;
    } else if !chars.is_empty() && is_align(chars[0]) {
        s.align = Some(chars[0]);
        i = 1;
    }
    if let Some(&c @ ('+' | '-' | ' ')) = chars.get(i) {
        s.sign = c;
        i += 1;
    }
    if chars.get(i) == Some(&'#') {
        s.alternate = true;
        i += 1;
    }
    if chars.get(i) == Some(&'0') {
        if s.align.is_none() {
            s.fill = '0';
            s.align = Some('=');
        }
        i += 1;
    }
    let digits = |i: &mut usize| -> Option<usize> {
        let start = *i;
        while chars.get(*i).is_some_and(|c| c.is_ascii_digit()) {
            *i += 1;
        }
        (start < *i).then(|| chars[start..*i].iter().collect::<String>().parse().ok()).flatten()
    };
    s.width = digits(&mut i).unwrap_or(0);
    if let Some(&c @ (',' | '_')) = chars.get(i) {
        s.grouping = Some(c);
        i += 1;
    }
    if chars.get(i) == Some(&'.') {
        i += 1;
        s.precision = Some(digits(&mut i)?);
    }
    if let Some(&c) = chars.get(i) {
        if !matches!(c, 'f' | 'F' | 'd' | 'e' | 'E' | 'g' | 'G' | '%' | 's') {
            return None;
        }
        s.ty = Some(c);
        i += 1;
    }
    (i == chars.len()).then_some(s)
}

/// Formats `v` according to the Python format spec `spec`.
pub fn format_value(spec: &str, v: &Value) -> String {
    let Some(s) = parse(spec) else {
        return display(v);
    };
    match v {
        Value::Float(x) => format_float(&s, *x),
        Value::Int(n) => format_int(&s, *n),
        Value::Bool(b) if !spec.is_empty() && s.ty != Some('s') => format_int(&s, i64::from(*b)),
        Value::Vec2([x, y]) => {
            let inner = Spec { width: 0, align: None, fill: ' ', ..s.clone() };
            let text = format!("({}, {})", format_float(&inner, *x), format_float(&inner, *y));
            pad(&s, "", &text, '<')
        }
        other => format_str(&s, &display(other)),
    }
}

/// Python `str()` of a value.
pub(crate) fn display(v: &Value) -> String {
    match v {
        Value::Float(x) => float_repr(*x),
        Value::Int(n) => n.to_string(),
        Value::Bool(b) => if *b { "True" } else { "False" }.into(),
        Value::Str(s) => s.clone(),
        Value::Vec2([x, y]) => format!("({}, {})", float_repr(*x), float_repr(*y)),
        Value::Color(c) => {
            let h = |x: f64| (x.clamp(0.0, 1.0) * 255.0).round() as u8;
            format!("#{:02x}{:02x}{:02x}{:02x}", h(c[0]), h(c[1]), h(c[2]), h(c[3]))
        }
        Value::List(items) => {
            let parts: Vec<String> = items.iter().map(display).collect();
            format!("[{}]", parts.join(", "))
        }
        Value::Object(id) => format!("<obj {id}>"),
        Value::None => "None".into(),
    }
}

/// Python `repr(float)`: shortest round-trip digits, `.0` for integral values,
/// scientific notation outside `[1e-4, 1e16)`.
fn float_repr(x: f64) -> String {
    if let Some(s) = non_finite(x, false) {
        return s;
    }
    let a = x.abs();
    if a != 0.0 && !(1e-4..1e16).contains(&a) {
        return python_exponent(&format!("{x:e}"));
    }
    let s = format!("{x}");
    if s.contains('.') { s } else { format!("{s}.0") }
}

fn non_finite(x: f64, upper: bool) -> Option<String> {
    let s = if x.is_nan() {
        "nan"
    } else if x.is_infinite() {
        if x > 0.0 { "inf" } else { "-inf" }
    } else {
        return None;
    };
    Some(if upper { s.to_uppercase() } else { s.into() })
}

/// Rewrites Rust exponent notation (`1.5e3`, `2e-7`) into Python's (`1.5e+03`, `2e-07`).
fn python_exponent(s: &str) -> String {
    let Some((mant, exp)) = s.split_once(['e', 'E']) else {
        return s.into();
    };
    let marker = if s.contains('E') { 'E' } else { 'e' };
    let (sign, digits) = match exp.strip_prefix('-') {
        Some(d) => ('-', d),
        None => ('+', exp.trim_start_matches('+')),
    };
    format!("{mant}{marker}{sign}{digits:0>2}")
}

fn format_int(s: &Spec, n: i64) -> String {
    match s.ty {
        Some('f' | 'F' | 'e' | 'E' | 'g' | 'G' | '%') => format_float(s, n as f64),
        _ => {
            let digits = n.unsigned_abs().to_string();
            number(s, n < 0, &digits, "")
        }
    }
}

fn format_float(s: &Spec, x: f64) -> String {
    let upper = matches!(s.ty, Some('F' | 'E' | 'G'));
    let neg = x.is_sign_negative() && !x.is_nan();
    if let Some(text) = non_finite(x.abs(), upper) {
        let suffix = if s.ty == Some('%') { "%" } else { "" };
        return number(&Spec { grouping: None, ..s.clone() }, neg, &text, suffix);
    }
    let a = x.abs();
    let (body, suffix) = match s.ty {
        Some('d') => ((a.round() as u128).to_string(), ""),
        Some('f' | 'F') => (format!("{a:.*}", s.precision.unwrap_or(6)), ""),
        Some('%') => (format!("{:.*}", s.precision.unwrap_or(6), a * 100.0), "%"),
        Some('e' | 'E') => (exponential(a, s.precision.unwrap_or(6), upper), ""),
        Some('g' | 'G') => (general(a, s.precision.unwrap_or(6), s.alternate, upper, false), ""),
        // No type: repr, or 'g'-like with at least one decimal when precision is given.
        _ => match s.precision {
            Some(p) => (general(a, p, s.alternate, false, true), ""),
            None => (float_repr(a), ""),
        },
    };
    let body = if s.alternate && !body.contains(['.', 'e', 'E']) && s.ty != Some('d') {
        format!("{body}.")
    } else {
        body
    };
    number(s, neg, &body, suffix)
}

fn exponential(a: f64, precision: usize, upper: bool) -> String {
    let s = python_exponent(&format!("{a:.precision$e}"));
    if upper { s.to_uppercase() } else { s }
}

/// Python's `g` presentation. `repr_like` is the no-type variant with a
/// precision, which keeps at least one digit after the decimal point.
fn general(a: f64, precision: usize, alternate: bool, upper: bool, repr_like: bool) -> String {
    let p = precision.max(1) as i32;
    let sci = format!("{a:.*e}", (p - 1) as usize);
    let exp: i32 = sci.split_once('e').map_or(0, |(_, e)| e.parse().unwrap_or(0));
    // The no-type form reserves one digit for the forced ".0".
    let limit = if repr_like { p - 1 } else { p };
    let out = if exp >= -4 && exp < limit {
        let decimals = (p - 1 - exp).max(0) as usize;
        let mut s = format!("{a:.decimals$}");
        if !alternate {
            s = strip_zeros(&s);
            if repr_like && !s.contains('.') {
                s.push_str(".0");
            }
        }
        s
    } else {
        let (mant, e) = sci.split_once('e').unwrap_or((&sci, "0"));
        let mant = match (alternate, mant.contains('.')) {
            (false, _) => strip_zeros(mant),
            (true, true) => mant.to_string(),
            (true, false) => format!("{mant}."),
        };
        python_exponent(&format!("{mant}e{e}"))
    };
    if upper { out.to_uppercase() } else { out }
}

fn strip_zeros(s: &str) -> String {
    if s.contains('.') {
        s.trim_end_matches('0').trim_end_matches('.').into()
    } else {
        s.into()
    }
}

/// Assembles sign, grouped digits and suffix, then pads to the width.
fn number(s: &Spec, neg: bool, body: &str, suffix: &str) -> String {
    let sign = match (neg, s.sign) {
        (true, _) => "-",
        (false, '+') => "+",
        (false, ' ') => " ",
        _ => "",
    };
    let split = body.find(|c: char| !c.is_ascii_digit()).unwrap_or(body.len());
    let (int, rest) = body.split_at(split);
    let Some(sep) = s.grouping else {
        return pad(s, sign, &format!("{body}{suffix}"), '>');
    };
    let mut int = int.to_string();
    // Zero padding with grouping pads the digits themselves (like Python).
    if s.align == Some('=') && s.fill == '0' {
        let fixed = sign.len() + rest.len() + suffix.len();
        while group(&int, sep).chars().count() + fixed < s.width {
            int.insert(0, '0');
        }
    }
    pad(s, sign, &format!("{}{rest}{suffix}", group(&int, sep)), '>')
}

fn group(int: &str, sep: char) -> String {
    let n = int.len();
    let mut out = String::with_capacity(n + n / 3);
    for (i, c) in int.chars().enumerate() {
        if i > 0 && (n - i).is_multiple_of(3) {
            out.push(sep);
        }
        out.push(c);
    }
    out
}

fn format_str(s: &Spec, text: &str) -> String {
    let text: String = match s.precision {
        Some(p) => text.chars().take(p).collect(),
        None => text.into(),
    };
    pad(s, "", &text, '<')
}

/// Pads `sign + body` to `s.width` using the spec's fill and alignment.
fn pad(s: &Spec, sign: &str, body: &str, default_align: char) -> String {
    let len = sign.chars().count() + body.chars().count();
    if len >= s.width {
        return format!("{sign}{body}");
    }
    let n = s.width - len;
    let fill = |k: usize| std::iter::repeat_n(s.fill, k).collect::<String>();
    match s.align.unwrap_or(default_align) {
        '<' => format!("{sign}{body}{}", fill(n)),
        '^' => format!("{}{sign}{body}{}", fill(n / 2), fill(n - n / 2)),
        '=' => format!("{sign}{}{body}", fill(n)),
        _ => format!("{}{sign}{body}", fill(n)),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_full_spec() {
        let s = parse("*^+#012,.3f").unwrap();
        assert_eq!(s.fill, '*');
        assert_eq!(s.align, Some('^'));
        assert_eq!(s.sign, '+');
        assert!(s.alternate);
        assert_eq!(s.width, 12);
        assert_eq!(s.grouping, Some(','));
        assert_eq!(s.precision, Some(3));
        assert_eq!(s.ty, Some('f'));
    }

    #[test]
    fn rejects_garbage() {
        assert!(parse("x").is_none());
        assert!(parse(".f").is_none());
        assert!(parse("5q").is_none());
        assert!(parse("").is_some());
    }

    #[test]
    fn exponent_rewrite() {
        assert_eq!(python_exponent("1.5e3"), "1.5e+03");
        assert_eq!(python_exponent("2e-7"), "2e-07");
        assert_eq!(python_exponent("1e100"), "1e+100");
    }
}
