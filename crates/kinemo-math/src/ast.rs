//! AST of the LaTeX math subset kinemo parses, and the command tables that
//! decide how commands become AST items.

/// One syntactic item of a math list.
#[derive(Clone, Debug, PartialEq)]
pub(crate) enum Ast {
    /// Passed through verbatim and never a part (spacing, `&`, `\\`, style
    /// switches...). `semantic` items take part in normalized TeX.
    Raw { tex: String, semantic: bool },
    /// A leaf: one symbol (`a`, `+`, `\alpha`), a number (`3.14`), or a command
    /// whose arguments are not math (`\text{if}`, `\operatorname{tr}`).
    Atom(String),
    /// `{...}`.
    Group(Vec<Ast>),
    /// A command with math arguments (`\frac{a}{b}`). `raw_args` are non-math
    /// arguments emitted before the math ones (`[3]` of `\sqrt[3]{x}`).
    Command { name: String, raw_args: String, args: Vec<Vec<Ast>> },
    /// Base with primes, `\limits`/`\nolimits` and scripts.
    Script {
        base: Option<Box<Ast>>,
        primes: usize,
        limits: Option<String>,
        sub: Option<Vec<Ast>>,
        sup: Option<Vec<Ast>>,
    },
    /// `\left<l> body \right<r>`.
    LeftRight { left: String, right: String, body: Vec<Ast> },
    /// `\begin{name}args body \end{name}`.
    Environment { name: String, args: String, body: Vec<Ast> },
    /// `\id{name}{body}`.
    Id { name: String, body: Vec<Ast> },
}

/// Commands whose arguments are math lists (and therefore parts).
pub(crate) const MATH_ARGUMENT_COMMANDS: &[&str] = &[
    "frac", "dfrac", "tfrac", "cfrac", "binom", "dbinom", "tbinom", "sqrt", "overset", "underset",
    "stackrel", "hat", "widehat", "tilde", "widetilde", "bar", "overline", "underline", "vec",
    "overrightarrow", "overleftarrow", "overleftrightarrow", "dot", "ddot", "dddot", "ddddot",
    "acute", "grave", "breve", "check", "widecheck", "mathring", "overbrace", "underbrace",
    "overbracket", "underbracket", "overgroup", "undergroup", "boxed", "fbox", "cancel", "bcancel",
    "xcancel", "mathbf", "mathrm", "mathit", "mathnormal", "mathcal", "mathbb", "mathfrak",
    "mathsf", "mathtt", "boldsymbol", "bm", "bold", "pmb", "Bbb", "mathbin", "mathrel", "mathop",
    "mathord", "mathopen", "mathclose", "mathpunct", "mathinner", "pmod", "pod", "phantom",
    "hphantom", "vphantom", "underbar", "set", "Set", "bra", "ket", "braket", "Bra", "Ket",
    "Braket", "xrightarrow", "xleftarrow", "xRightarrow", "xLeftarrow", "xleftrightarrow",
    "xLeftrightarrow", "xmapsto", "xlongequal", "xhookrightarrow", "xhookleftarrow",
    "xtwoheadrightarrow", "xtwoheadleftarrow",
];


/// Spacing and bookkeeping commands: emitted verbatim, no part, no meaning for matching.
pub(crate) const INVISIBLE_COMMANDS: &[&str] = &[
    "quad", "qquad", "enspace", "thinspace", "medspace", "thickspace", "negthinspace",
    "negmedspace", "negthickspace", "negthinmedspace", "nobreakspace", "hfill", "relax",
    "nonumber", "notag", "hline", "cr", "allowbreak",
];

/// Invisible commands that take one argument (`\hspace{1em}`, `\color{red}`).
pub(crate) const INVISIBLE_COMMANDS_WITH_ARGUMENT: &[&str] =
    &["hspace", "hspace*", "vspace", "vspace*", "label", "tag", "tag*", "color"];

pub(crate) fn is_x_arrow(name: &str) -> bool {
    name.starts_with('x') && name.contains("arrow") || name == "xmapsto" || name == "xlongequal"
}

