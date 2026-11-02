#!/usr/bin/env bash
# Regenerate assets/fonts/subset/ from the full DejaVu faces, for the
# `subset-fonts` feature of kinemo-text: Latin (with Latin-1 and
# Extended-A), combining marks, Greek, phonetic super/subscripts,
# punctuation, super/subscripts, currency, letterlike symbols, number forms,
# arrows, mathematical operators, technical symbols and geometric shapes.
# Hinting is dropped: kinemo renders outlines and never uses it.
#
# Needs fontTools: `pip install fonttools`.
set -euo pipefail
cd "$(dirname "$0")/../assets/fonts"
mkdir -p subset
UNICODES="U+0020-007E,U+00A0-00FF,U+0100-017F,U+0300-036F,U+0370-03FF,U+1D00-1DBF,U+2000-206F,U+2070-209F,U+20A0-20CF,U+2100-214F,U+2150-218F,U+2190-21FF,U+2200-22FF,U+2300-23FF,U+25A0-25FF"
for f in DejaVuSans DejaVuSans-Bold DejaVuSans-Oblique DejaVuSansMono; do
  pyftsubset "$f.ttf" --unicodes="$UNICODES" --layout-features='*' \
    --no-hinting --desubroutinize --output-file="subset/$f.ttf"
done
