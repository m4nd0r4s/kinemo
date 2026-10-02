// Definitions for the names mitex emits that are not typst built-ins.
// Written for kinemo against typst 0.15; it plays the role of mitex's own
// typst package (`mitex-scope`), which is not available offline.
// Colors requested in TeX (\color, \textcolor) are ignored: kinemo colors parts
// itself, and fill colors are used as part markers.

#let mitex-plain(c) = {
  if c == none { "" } else if type(c) == str { c } else if type(c) != content { str(c) } else if c.has("text") {
    if type(c.text) == str { c.text } else { mitex-plain(c.text) }
  } else if c.has("children") { c.children.fold("", (acc, x) => acc + mitex-plain(x)) } else if c.has("body") {
    mitex-plain(c.body)
  } else if c == [ ] { " " } else { "" }
}
#let mitex-concat(items) = items.fold([], (acc, x) => acc + x)
#let mitex-join(args) = {
  let p = args.pos()
  if p.len() == 0 { [] } else { p.slice(1).fold(p.at(0), (acc, x) => acc + [,] + x) }
}
#let mitex-unbracket(c) = {
  if type(c) == content and c.has("children") {
    let ch = c.children.filter(x => x != [ ])
    if ch.len() >= 2 and mitex-plain(ch.first()) == "[" and mitex-plain(ch.last()) == "]" {
      return mitex-concat(ch.slice(1, -1))
    }
  }
  c
}

// Roots, fractions, binomials.
#let mitexsqrt(..a) = {
  let p = a.pos()
  if p.len() >= 2 { math.root(mitex-unbracket(p.at(0)), p.at(1)) } else if p.len() == 1 { math.sqrt(p.at(0)) } else { math.sqrt([]) }
}
#let dfrac(a, b) = math.display(math.frac(a, b))
#let tfrac(a, b) = math.inline(math.frac(a, b))
#let cfrac(a, b) = math.display(math.frac(math.display(a), math.display(b)))
#let dbinom(a, b) = math.display(math.binom(a, b))
#let tbinom(a, b) = math.inline(math.binom(a, b))
#let atop(a, b) = math.vec(delim: none, a, b)
#let brace(a, b) = math.vec(delim: "{", a, b)
#let brack(a, b) = math.vec(delim: "[", a, b)

// Styles and fonts.
#let mitexdisplay(..a) = math.display(mitex-join(a))
#let mitexinline(..a) = math.inline(mitex-join(a))
#let mitexscript(..a) = math.script(mitex-join(a))
#let mitexsscript(..a) = math.sscript(mitex-join(a))
#let mitexmathbf(it) = math.upright(math.bold(it))
#let mitexbold(..a) = math.upright(math.bold(mitex-join(a)))
#let mitexupright(..a) = math.upright(mitex-join(a))
#let mitexitalic(..a) = math.italic(mitex-join(a))
#let mitexcal(..a) = math.cal(mitex-join(a))
#let mitexfrak(..a) = math.frak(mitex-join(a))
#let mitexsans(..a) = math.sans(mitex-join(a))
#let mitexmono(..a) = math.mono(mitex-join(a))
#let mitexcolor(color, ..a) = mitex-join(a)
// Part markers: `\textcolor{<node id>}{...}` → fill color encoding the id.
#let colortext(id, body) = {
  let n = int(mitex-plain(id).replace(" ", ""))
  text(fill: rgb(calc.quo(n, 65536), calc.rem(calc.quo(n, 256), 256), calc.rem(n, 256)), body)
}
#let colorbox(color, body) = body
#let textmath(it) = it
#let textbf(it) = text(weight: "bold", it)
#let textit(it) = text(style: "italic", it)
#let texttt(it) = text(font: "DejaVu Sans Mono", it)
#let textsf(it) = it
#let textrm(it) = it
#let textup(it) = text(style: "normal", it)
#let textmd(it) = text(weight: "regular", it)
#let textnormal(it) = it
#let mitexcite(..a) = []
#let mitexref(..a) = []
#let miteximage(..a) = []
#let mitexlabel(..a) = []
#let mitexcaption(..a) = []
#let toprule(..a) = []
#let midrule(..a) = []
#let bottomrule(..a) = []
#let textwidth = []
#let TeX = text(font: "New Computer Modern")[TeX]
#let LaTeX = text(font: "New Computer Modern")[LaTeX]
#let KaTeX = text(font: "New Computer Modern")[KaTeX]

// Spacing.
#let negthinspace = h(-0.1667em)
#let negmedspace = h(-0.2222em)
#let negthickspace = h(-0.2778em)
#let negthinmedspace = h(-0.2222em)
#let enspace = h(0.5em)
#let hspace(..a) = h(0.5em)
#let vspace(..a) = []
#let phantom(it) = hide($it$)
#let hphantom(it) = box(height: 0pt, hide($it$))
#let vphantom(it) = box(width: 0pt, hide($it$))
#let raisebox(..a) = a.pos().last()
#let hbox(it) = it
#let mathclap(it) = it

// Delimiter sizes.
#let big(it) = math.lr(it, size: 1.2em)
#let Big(it) = math.lr(it, size: 1.8em)
#let bigg(it) = math.lr(it, size: 2.4em)
#let Bigg(it) = math.lr(it, size: 3em)
#let middle(it) = math.mid(it)

// Matrices and environments.
#let matrix(..a) = math.mat(delim: none, ..a)
#let pmatrix(..a) = math.mat(delim: "(", ..a)
#let bmatrix(..a) = math.mat(delim: "[", ..a)
#let Bmatrix(..a) = math.mat(delim: "{", ..a)
#let vmatrix(..a) = math.mat(delim: "|", ..a)
#let Vmatrix(..a) = math.mat(delim: "‖", ..a)
#let smallmatrix(..a) = math.inline(math.mat(delim: none, ..a))
#let mitexarray(arg0: none, ..a) = {
  let spec = mitex-plain(arg0).replace(" ", "").replace("|", "")
  let al = if spec.starts-with("l") { left } else if spec.starts-with("r") { right } else { center }
  math.mat(delim: none, align: al, ..a)
}
#let aligned(arg0: none, ..a) = mitex-join(a)
#let alignedat(arg0: none, ..a) = mitex-join(a)
#let rcases(..a) = math.cases(reverse: true, ..a)
#let substack(it) = {
  if type(it) == content and it.has("children") {
    let rows = it.children.split(linebreak())
    math.vec(delim: none, gap: 0.1em, ..rows.map(mitex-concat))
  } else { it }
}

// Braces, accents, arrows.
#let mitexoverbrace(it) = math.limits(math.overbrace(it))
#let mitexunderbrace(it) = math.limits(math.underbrace(it))
#let mitexoverbracket(it) = math.limits(math.overbracket(it))
#let mitexunderbracket(it) = math.limits(math.underbracket(it))
#let overgroup(it) = math.limits(math.overparen(it))
#let undergroup(it) = math.limits(math.underparen(it))
#let overset(a, b) = math.attach(math.limits(b), t: a)
#let underset(a, b) = math.attach(math.limits(b), b: a)
#let stackrel(a, b) = math.attach(math.limits(b), t: a)
#let mathring(it) = math.accent(it, "˚")
#let overleftharpoon(it) = math.accent(it, sym.harpoon.lt)
#let overrightharpoon(it) = math.accent(it, sym.harpoon.rt)
#let overleftrightarrow(it) = math.accent(it, sym.arrow.l.r)
#let overlinesegment(it) = math.overline(it)
#let underbar(it) = math.underline(it)
#let mitex-xarrow(arrow, ..a) = {
  let p = a.pos()
  let top = if p.len() > 0 { p.last() } else { none }
  math.class("relation", math.attach(math.limits(math.stretch(arrow, size: 100% + 0.8em)), t: top))
}
#let xrightarrow(..a) = mitex-xarrow(sym.arrow.r, ..a)
#let xleftarrow(..a) = mitex-xarrow(sym.arrow.l, ..a)
#let xRightarrow(..a) = mitex-xarrow(sym.arrow.r.double, ..a)
#let xLeftarrow(..a) = mitex-xarrow(sym.arrow.l.double, ..a)
#let xleftrightarrow(..a) = mitex-xarrow(sym.arrow.l.r, ..a)
#let xLeftrightarrow(..a) = mitex-xarrow(sym.arrow.l.r.double, ..a)
#let xmapsto(..a) = mitex-xarrow(sym.arrow.r.bar, ..a)
#let xlongequal(..a) = mitex-xarrow(sym.eq, ..a)
#let xhookrightarrow(..a) = mitex-xarrow(sym.arrow.r.hook, ..a)
#let xhookleftarrow(..a) = mitex-xarrow(sym.arrow.l.hook, ..a)
#let xtwoheadrightarrow(..a) = mitex-xarrow(sym.arrow.r.twohead, ..a)
#let xtwoheadleftarrow(..a) = mitex-xarrow(sym.arrow.l.twohead, ..a)
#let xrightharpoonup(..a) = mitex-xarrow(sym.harpoon.rt, ..a)
#let xrightharpoondown(..a) = mitex-xarrow(sym.harpoon.rb, ..a)
#let xleftharpoonup(..a) = mitex-xarrow(sym.harpoon.lt, ..a)
#let xleftharpoondown(..a) = mitex-xarrow(sym.harpoon.lb, ..a)
#let xleftrightharpoons(..a) = mitex-xarrow(sym.harpoons.ltrb, ..a)
#let xrightleftharpoons(..a) = mitex-xarrow(sym.harpoons.rtlb, ..a)
#let xtofrom(..a) = mitex-xarrow(sym.arrows.rl, ..a)

// Boxes and cancellation.
#let boxed(it) = context box(stroke: 0.04em + text.fill, inset: 0.25em, $display(it)$)
#let fbox(it) = boxed(it)
#let bcancel(it) = math.cancel(it, inverted: true)
#let xcancel(it) = math.cancel(it, cross: true)
#let sout(it) = math.cancel(it, angle: 90deg)

// Classes.
#let mathbin(it) = math.class("binary", it)
#let mathrel(it) = math.class("relation", it)
#let mathop(it) = math.class("large", it)
#let mathord(it) = math.class("normal", it)
#let mathopen(it) = math.class("opening", it)
#let mathclose(it) = math.class("closing", it)
#let mathpunct(it) = math.class("punctuation", it)
#let mathinner(it) = it

// Operators.
#let operatorname(it) = math.op(math.upright(it))
#let operatornamewithlimits(it) = math.op(math.upright(it), limits: true)
#let arcctg = math.op("arcctg")
#let arctg = math.op("arctg")
#let cosec = math.op("cosec")
#let cotg = math.op("cotg")
#let ch = math.op("ch")
#let sh = math.op("sh")
#let th = math.op("th")
#let cth = math.op("cth")
#let argmax = math.op("arg max", limits: true)
#let argmin = math.op("arg min", limits: true)
#let injlim = math.op("inj lim", limits: true)
#let projlim = math.op("proj lim", limits: true)
#let plim = math.op("plim", limits: true)
#let pmod(it) = $quad (mod it)$
#let pod(it) = $quad (it)$

// Physics (braket) and sets.
#let mitexset(it) = $lr({it})$
#let Set(it) = $lr({it})$
#let bra(it) = $lr(chevron.l it |)$
#let Bra(it) = $lr(chevron.l it |)$
#let ket(it) = $lr(| it chevron.r)$
#let Ket(it) = $lr(| it chevron.r)$
#let braket(it) = $lr(chevron.l it chevron.r)$
#let Braket(it) = $lr(chevron.l it chevron.r)$

// Symbols.
#let smallint = sym.integral
#let thickapprox = sym.approx
#let thicksim = sym.tilde.op
#let varGamma = math.italic(sym.Gamma)
#let varDelta = math.italic(sym.Delta)
#let varTheta = math.italic(sym.Theta)
#let varLambda = math.italic(sym.Lambda)
#let varXi = math.italic(sym.Xi)
#let varPi = math.italic(sym.Pi)
#let varSigma = math.italic(sym.Sigma)
#let varUpsilon = math.italic(sym.Upsilon)
#let varPhi = math.italic(sym.Phi)
#let varPsi = math.italic(sym.Psi)
#let varOmega = math.italic(sym.Omega)
