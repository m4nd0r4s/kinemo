//! Morph matching between two token sequences.
//!
//! 1. Line diff: lines (as sequences of `(text, kind)`; indentation ignored)
//!    are matched by LCS; every token of a matched line pairs with its
//!    counterpart, so unchanged lines slide as a whole.
//! 2. Token diff: inside each changed region between matched lines, tokens
//!    are matched by LCS on `(text, kind)`, so a renamed variable keeps the
//!    surrounding tokens travelling.
//!
//! Unmatched old tokens fade out; unmatched new tokens fade in.

use std::collections::HashMap;

use crate::tokens::{Token, TokenKind};

/// Above this many DP cells, LCS falls back to common prefix/suffix only.
const LCS_CELL_LIMIT: usize = 16_000_000;

/// Pairs `(old token index, new token index)` that should travel, in
/// increasing order of both indices.
pub fn match_tokens(old: &[Token], new: &[Token]) -> Vec<(usize, usize)> {
    let old_lines = group_lines(old);
    let new_lines = group_lines(new);

    let mut line_ids = HashMap::new();
    let old_ids: Vec<usize> = old_lines
        .iter()
        .map(|range| line_id(&mut line_ids, old, range))
        .collect();
    let new_ids: Vec<usize> = new_lines
        .iter()
        .map(|range| line_id(&mut line_ids, new, range))
        .collect();

    let mut pairs = Vec::new();
    let (mut old_cursor, mut new_cursor) = (0, 0);
    for (old_line, new_line) in longest_common_subsequence(&old_ids, &new_ids) {
        let (old_range, new_range) = (&old_lines[old_line], &new_lines[new_line]);
        match_region(
            old,
            new,
            old_cursor..old_range.start,
            new_cursor..new_range.start,
            &mut pairs,
        );
        pairs.extend(old_range.clone().zip(new_range.clone()));
        old_cursor = old_range.end;
        new_cursor = new_range.end;
    }
    match_region(
        old,
        new,
        old_cursor..old.len(),
        new_cursor..new.len(),
        &mut pairs,
    );
    pairs
}

type LineKey<'a> = Vec<(&'a str, TokenKind)>;

/// Small integer id per distinct line content, so the line LCS compares ids.
fn line_id<'a>(
    ids: &mut HashMap<LineKey<'a>, usize>,
    tokens: &'a [Token],
    range: &std::ops::Range<usize>,
) -> usize {
    let key: LineKey<'a> = tokens[range.clone()]
        .iter()
        .map(|token| (token.text.as_str(), token.kind))
        .collect();
    let next = ids.len();
    *ids.entry(key).or_insert(next)
}

/// Token index ranges of each line that has tokens, in order.
fn group_lines(tokens: &[Token]) -> Vec<std::ops::Range<usize>> {
    let mut lines: Vec<std::ops::Range<usize>> = Vec::new();
    for (index, token) in tokens.iter().enumerate() {
        match lines.last_mut() {
            Some(range) if tokens[range.start].line == token.line => range.end = index + 1,
            _ => lines.push(index..index + 1),
        }
    }
    lines
}

fn match_region(
    old: &[Token],
    new: &[Token],
    old_range: std::ops::Range<usize>,
    new_range: std::ops::Range<usize>,
    pairs: &mut Vec<(usize, usize)>,
) {
    if old_range.is_empty() || new_range.is_empty() {
        return;
    }
    let old_keys: Vec<(&str, TokenKind)> = old[old_range.clone()]
        .iter()
        .map(|t| (t.text.as_str(), t.kind))
        .collect();
    let new_keys: Vec<(&str, TokenKind)> = new[new_range.clone()]
        .iter()
        .map(|t| (t.text.as_str(), t.kind))
        .collect();
    pairs.extend(
        longest_common_subsequence(&old_keys, &new_keys)
            .into_iter()
            .map(|(a, b)| (a + old_range.start, b + new_range.start)),
    );
}

/// Index pairs of a longest common subsequence (deterministic tie-breaking).
fn longest_common_subsequence<T: Eq>(a: &[T], b: &[T]) -> Vec<(usize, usize)> {
    let prefix = a.iter().zip(b).take_while(|(x, y)| x == y).count();
    let suffix = a[prefix..]
        .iter()
        .rev()
        .zip(b[prefix..].iter().rev())
        .take_while(|(x, y)| x == y)
        .count();
    let (middle_a, middle_b) = (&a[prefix..a.len() - suffix], &b[prefix..b.len() - suffix]);

    let mut pairs: Vec<(usize, usize)> = (0..prefix).map(|i| (i, i)).collect();
    let (n, m) = (middle_a.len(), middle_b.len());
    if n > 0 && m > 0 && (n + 1) * (m + 1) <= LCS_CELL_LIMIT {
        // lengths[i][j] = LCS length of middle_a[i..] and middle_b[j..].
        let width = m + 1;
        let mut lengths = vec![0u32; (n + 1) * width];
        for i in (0..n).rev() {
            for j in (0..m).rev() {
                lengths[i * width + j] = if middle_a[i] == middle_b[j] {
                    lengths[(i + 1) * width + j + 1] + 1
                } else {
                    lengths[(i + 1) * width + j].max(lengths[i * width + j + 1])
                };
            }
        }
        let (mut i, mut j) = (0, 0);
        while i < n && j < m {
            if middle_a[i] == middle_b[j] {
                pairs.push((prefix + i, prefix + j));
                i += 1;
                j += 1;
            } else if lengths[(i + 1) * width + j] >= lengths[i * width + j + 1] {
                i += 1;
            } else {
                j += 1;
            }
        }
    }
    let (a_tail, b_tail) = (a.len() - suffix, b.len() - suffix);
    pairs.extend((0..suffix).map(|k| (a_tail + k, b_tail + k)));
    pairs
}
