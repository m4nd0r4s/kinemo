//! Word segmentation and greedy line breaking.

/// Char ranges of whitespace-separated words, plus the word index of each char
/// (`usize::MAX` for whitespace).
pub(crate) fn words(chars: &[char]) -> (Vec<(usize, usize)>, Vec<usize>) {
    let n = chars.len();
    let mut words = Vec::new();
    let mut word_of = vec![usize::MAX; n];
    let mut i = 0;
    while i < n {
        if chars[i].is_whitespace() {
            i += 1;
            continue;
        }
        let s = i;
        while i < n && !chars[i].is_whitespace() {
            word_of[i] = words.len();
            i += 1;
        }
        words.push((s, i));
    }
    (words, word_of)
}

/// Break into lines: char ranges `[start, end)`. Explicit '\n' always breaks;
/// with `max_width`, words are wrapped greedily at whitespace (whitespace at a
/// wrap point belongs to no line). A word longer than the width overflows.
/// `char_adv` is the advance attributed to each char.
pub(crate) fn break_lines(chars: &[char], char_adv: &[f64], max_width: Option<f64>) -> Vec<(usize, usize)> {
    let n = chars.len();
    let mut lines = Vec::new();
    let mut para_start = 0;
    loop {
        let para_end = (para_start..n).find(|&k| chars[k] == '\n').unwrap_or(n);
        match max_width {
            None => lines.push((para_start, para_end)),
            Some(maxw) => wrap_paragraph(chars, char_adv, para_start, para_end, maxw, &mut lines),
        }
        if para_end >= n {
            break;
        }
        para_start = para_end + 1;
    }
    lines
}

fn wrap_paragraph(chars: &[char], adv: &[f64], start: usize, end: usize, maxw: f64, out: &mut Vec<(usize, usize)>) {
    let mut line_start = start;
    let mut line_end = start; // end of the last word on the current line
    let mut has_word = false;
    let mut k = start;
    while k < end {
        if chars[k].is_whitespace() {
            k += 1;
            continue;
        }
        let ws = k;
        while k < end && !chars[k].is_whitespace() {
            k += 1;
        }
        let candidate: f64 = adv[line_start..k].iter().sum();
        if has_word && candidate > maxw + 1e-9 {
            out.push((line_start, line_end));
            line_start = ws;
        }
        line_end = k;
        has_word = true;
    }
    out.push(if has_word { (line_start, line_end) } else { (start, end) });
}

/// Advance width of a line, excluding trailing whitespace.
pub(crate) fn line_width(chars: &[char], char_adv: &[f64], (s, e): (usize, usize)) -> f64 {
    let mut e2 = e;
    while e2 > s && chars[e2 - 1].is_whitespace() {
        e2 -= 1;
    }
    char_adv[s..e2].iter().sum()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn greedy() {
        let chars: Vec<char> = "aa bb cc".chars().collect();
        let adv = vec![1.0; chars.len()];
        assert_eq!(break_lines(&chars, &adv, None), vec![(0, 8)]);
        assert_eq!(break_lines(&chars, &adv, Some(5.0)), vec![(0, 5), (6, 8)]);
        assert_eq!(break_lines(&chars, &adv, Some(1.0)), vec![(0, 2), (3, 5), (6, 8)]);
        let (w, _) = words(&chars);
        assert_eq!(w, vec![(0, 2), (3, 5), (6, 8)]);
    }
}
