# Examples

Complete scenes from [`examples/`](../../examples). Each one passes `kinemo check --strict`
and is part of the test suite. Frames below are rendered at draft quality by
`scripts/build_gallery.py`.

| Example | Shows |
| --- | --- |
| [Hello](hello.md) | The smallest scene: write a title, then animate its color and scale. |
| [Bubble sort](bubble_sort.md) | Ordinary Python logic in the build phase drives a sorting animation: bars reflow when swapped, comparisons are highlighted with `s.during`, and `s.tempo` accelerates the run. |
| [Derivative](derivative.md) | A tangent slides along a curve while a reactive label shows the slope; the axes zoom at the end. |
| [Pythagoras](pythagoras.md) | Squares built on the sides of a right triangle, a clip, a highlight with `s.during` and a structural morph between two equations. |
| [A day with solar + battery](solar_day.md) | A component integrates power into a state of charge, fires `full`/`empty` events with hysteresis, and reads its clock from a context; the load curve comes from a polars DataFrame. |
| [Bouncing ball](bounce.md) | A fixed-step simulation with typed events; each impact squashes the ball and the script waits for the third bounce. |
| [Parametric polygon](polygon.md) | A scene parameter drives the number of sides (`kinemo render --param n=8`). |
| [Energy bar chart](energy.md) | A bar chart built from a polars DataFrame transitions to new data: bars grow, reorder and enter by key. |
| [Vector field](field.md) | A vector field, animated stream lines and thousands of points with per-point colors, all evaluated natively. |
