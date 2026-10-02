//! Text queries used to address parts (`txt["world"]`, `txt.find_all`).

/// Char ranges `[start, end)` of all non-overlapping occurrences of `needle`
/// in `plain`. An empty needle matches nothing.
pub fn ranges_of(plain: &str, needle: &str) -> Vec<(usize, usize)> {
    if needle.is_empty() {
        return Vec::new();
    }
    let nlen = needle.chars().count();
    let mut out = Vec::new();
    let mut char_pos = 0usize;
    let mut last_byte = 0usize;
    for (bi, _) in plain.match_indices(needle) {
        char_pos += plain[last_byte..bi].chars().count();
        out.push((char_pos, char_pos + nlen));
        char_pos += nlen;
        last_byte = bi + needle.len();
    }
    out
}
