#![allow(clippy::approx_constant)] // reference inputs, not π

//! `format_value` against reference outputs produced by CPython's `format()`.

use kinemo_eval::format::format_value;
use kinemo_ir::Value;

fn check(cases: &[(&str, Value, &str)]) {
    for (spec, v, expected) in cases {
        assert_eq!(format_value(spec, v), *expected, "format({v:?}, {spec:?})");
    }
}

fn f(x: f64) -> Value {
    Value::Float(x)
}

fn i(n: i64) -> Value {
    Value::Int(n)
}

fn s(x: &str) -> Value {
    Value::Str(x.into())
}

#[test]
fn float_repr_without_spec() {
    check(&[
        ("", f(1.0), "1.0"),
        ("", f(0.1), "0.1"),
        ("", f(1e16), "1e+16"),
        ("", f(1.5e-5), "1.5e-05"),
        ("", f(123456.789), "123456.789"),
        ("", f(-0.0), "-0.0"),
        ("", i(3), "3"),
    ]);
}

#[test]
fn fixed_point() {
    check(&[
        (".2f", f(3.14159), "3.14"),
        (".0f", f(2.5), "2"),
        (".0f", f(3.5), "4"),
        ("f", f(1.0), "1.000000"),
        (".2f", f(-0.001), "-0.00"),
        ("+.1f", f(2.0), "+2.0"),
        (" .1f", f(2.0), " 2.0"),
        ("#.0f", f(5.0), "5."),
        (".2f", i(7), "7.00"),
    ]);
}

#[test]
fn width_fill_align() {
    check(&[
        ("8.3f", f(3.14159), "   3.142"),
        ("<8.2f", f(1.5), "1.50    "),
        ("^9.1f", f(1.5), "   1.5   "),
        ("*^9.1f", f(1.5), "***1.5***"),
        ("=+8.1f", f(1.5), "+    1.5"),
        ("08.2f", f(-3.14159), "-0003.14"),
    ]);
}

#[test]
fn integers_and_grouping() {
    check(&[
        (",", i(1234567), "1,234,567"),
        (",.2f", f(1234567.891), "1,234,567.89"),
        ("_", i(1234567), "1_234_567"),
        ("010,", i(1234), "00,001,234"),
        ("09,", i(1234), "0,001,234"),
        ("d", i(42), "42"),
        ("5d", i(42), "   42"),
        ("05d", i(-42), "-0042"),
        ("+d", i(5), "+5"),
    ]);
}

#[test]
fn exponent() {
    check(&[
        ("e", f(1234.5), "1.234500e+03"),
        (".2e", f(0.000123), "1.23e-04"),
        ("E", f(1234.5), "1.234500E+03"),
        (".3e", f(0.0), "0.000e+00"),
        ("e", i(5), "5.000000e+00"),
    ]);
}

#[test]
fn general() {
    check(&[
        ("g", i(1234567), "1.23457e+06"),
        ("g", i(123456), "123456"),
        ("g", f(0.0001234), "0.0001234"),
        ("g", f(0.00001234), "1.234e-05"),
        (".3g", f(3.14159), "3.14"),
        ("G", f(1e-10), "1E-10"),
        ("g", f(0.0), "0"),
        (".3g", f(0.0), "0"),
        ("#.3g", f(0.0), "0.00"),
        ("#g", f(1.0), "1.00000"),
        (".2g", i(100), "1e+02"),
    ]);
}

#[test]
fn no_type_with_precision() {
    check(&[
        (".3", f(1.0), "1.0"),
        (".2", f(1234.5), "1.2e+03"),
        (".3", f(3.14159), "3.14"),
        (".1", f(0.0), "0e+00"),
        (".2", f(0.0), "0.0"),
        (".1", f(10.0), "1e+01"),
        (".1", f(1.0), "1e+00"),
        (".2", f(1.0), "1.0"),
        (".1", f(0.5), "0.5"),
        ("#.1", f(0.0), "0.e+00"),
    ]);
}

#[test]
fn percent() {
    check(&[("%", f(0.25), "25.000000%"), (".1%", f(0.256), "25.6%"), (".0%", i(1), "100%")]);
}

#[test]
fn non_finite() {
    check(&[("f", f(f64::INFINITY), "inf"), ("F", f(f64::NAN), "NAN"), ("8.2f", f(f64::NEG_INFINITY), "    -inf")]);
}

#[test]
fn strings() {
    check(&[
        ("s", s("hi"), "hi"),
        ("5", s("hi"), "hi   "),
        (">5", s("hi"), "   hi"),
        ("^6", s("hi"), "  hi  "),
        (".1s", s("hello"), "h"),
        ("-<5", s("ab"), "ab---"),
        ("", s("x"), "x"),
    ]);
}

#[test]
fn bools() {
    check(&[("", Value::Bool(true), "True"), ("d", Value::Bool(true), "1"), (".1f", Value::Bool(true), "1.0")]);
}

#[test]
fn other_values() {
    check(&[
        ("", Value::Vec2([1.0, 2.5]), "(1.0, 2.5)"),
        (".1f", Value::Vec2([1.0, 2.25]), "(1.0, 2.2)"),
        ("", Value::None, "None"),
        ("", Value::List(vec![i(1), s("a")]), "[1, a]"),
        ("", Value::Color([1.0, 0.0, 0.0, 1.0]), "#ff0000ff"),
    ]);
}

#[test]
fn invalid_spec_falls_back_to_str() {
    check(&[("zz", f(1.5), "1.5"), (".2q", i(3), "3")]);
}
