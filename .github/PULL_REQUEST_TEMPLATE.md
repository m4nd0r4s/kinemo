## What and why

<!-- What this changes, and the problem it solves. Link the issue if there is one. -->

## Checks

- [ ] `cargo clippy --workspace --all-targets -- -D warnings` and `cargo test --workspace`
- [ ] `python -m pytest -q` and `pyright python/kinemo`
- [ ] Docs regenerated if a public symbol, docstring or example changed (see CONTRIBUTING.md)
- [ ] A new user mistake has a diagnostic code, a fix and a test
