# Lint corpus

Scenes written the way real explainer videos are (bit registers, speech bubbles, narrated
dials, digit changes, sorting rows near an edge), each with the diagnostics `kinemo check`
must report on its first line: `# expect: W1001` or `# expect: none`.

`tests/python/test_lint_corpus.py` checks every scene. A lint change is judged by what it
does here: false positives (a code reported that is not expected) and misses (an expected
code not reported). Add a scene when a lint misfires in real use.
