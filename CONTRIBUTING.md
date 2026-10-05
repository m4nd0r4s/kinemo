# Contributing to kinemo

Thanks for helping. Bug reports, examples that confuse you, docs fixes and code are all
welcome. For a larger change, open an issue first so the design can be agreed before the work.

## Set up

Requirements: stable Rust, Python 3.11 or newer, [uv](https://github.com/astral-sh/uv) and
`ffmpeg`.

```bash
uv venv .venv
uv pip install --python .venv/bin/python maturin pytest pyright numpy polars
source .venv/bin/activate
maturin develop            # rebuild after changing Rust code
```

## Check your change

```bash
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
python -m pytest -q
pyright python/kinemo
```

The Python tests include golden frames (`tests/golden/`, byte-identical on the CPU renderer)
and performance budgets (`tests/python/test_performance.py`; `KINEMO_SKIP_PERF=1` skips them on
a busy machine). After an intentional change to rendering, regenerate the golden frames with
`KINEMO_UPDATE_GOLDEN=1 pytest tests/python/test_golden.py` and say so in the pull request.

## Measure performance

`python -m benchmarks` times every stage of the example scenes and of `benchmarks/scenes`
(heavy text, math, code and mass objects, and a ten-minute episode-like scene): build, the
lints, one draft and one final frame, rendering on every core and the end-to-end video.
`--quick` skips the long scene and the videos, names filter the scenes, and `--json` keeps the
numbers to compare before and after a change. CI runs it on every push to `main` (job summary
and a `benchmarks-<sha>` artifact).

Inside one frame, `cargo run --release -p kinemo-render --example stage_timings -- scene.json`
splits the display list from rasterization (`scene.json` from `scene.builder.to_json()`).

## Docs are generated, and tested

- The API reference and `docs/llms.txt` come from the code. After changing a public symbol, a
  docstring or a canonical example (`python/kinemo/docs/examples/`), run
  `python -m kinemo.docs.markdown docs/reference` and `python -m kinemo.docs.llms > docs/llms.txt`;
  the tests fail when they drift.
- `docs/examples/` comes from `scripts/build_gallery.py`.
- Every relative link and `#anchor` in the docs is checked by `tests/python/test_doc_links.py`.
- The website (`website/`) builds from the same docs; see `website/README.md`.

## Conventions

- **English everywhere:** code, comments, docstrings, docs, commit messages.
- **Descriptive names:** full words, no single-letter variables outside tiny comprehensions.
- **Small modules:** split a file before it grows past a few hundred lines.
- **Every error is a diagnostic.** A new mistake users can make gets a stable code
  (`K…` for errors, `W…` for lints) in `python/kinemo/diagnostics/catalog.py`, a message that
  says what to do, a fix when one is safe, and a test that triggers it.
- **The public API is typed.** `tests/python/test_typing.py` runs Pyright in strict mode over
  user-style scenes and every docs example.
- **Commits** are small and focused, with a short message in the imperative
  ("Fix K0401 span for chained calls").

## Licensing

kinemo is dual-licensed under MIT or Apache-2.0. Unless you state otherwise, any contribution
you submit for inclusion is dual-licensed as above, without any additional terms. When you add
or update a Rust dependency, run `scripts/third_party_licenses.py` and commit
`THIRD_PARTY_LICENSES.md`.
