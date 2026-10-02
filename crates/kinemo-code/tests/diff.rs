use kinemo_code::{match_tokens, tokenize, Token};

fn tokens(source: &str) -> Vec<Token> {
    tokenize(source, "python").unwrap()
}

fn matched_texts(old: &[Token], new: &[Token], pairs: &[(usize, usize)]) {
    for &(a, b) in pairs {
        assert_eq!(old[a].text, new[b].text);
        assert_eq!(old[a].kind, new[b].kind);
    }
    for pair in pairs.windows(2) {
        assert!(
            pair[0].0 < pair[1].0 && pair[0].1 < pair[1].1,
            "pairs must be monotonic"
        );
    }
}

#[test]
fn identical_sources_match_everything() {
    let old = tokens("a = 1\nb = a + 2\n");
    let pairs = match_tokens(&old, &old);
    assert_eq!(pairs, (0..old.len()).map(|i| (i, i)).collect::<Vec<_>>());
}

#[test]
fn inserted_line_is_unmatched_and_others_match() {
    let old = tokens("x = 1\ny = 2\nprint(x + y)\n");
    let new = tokens("x = 1\ny = 2\nz = 3\nprint(x + y)\n");
    let pairs = match_tokens(&old, &new);
    matched_texts(&old, &new, &pairs);
    assert_eq!(pairs.len(), old.len(), "every old token is unchanged");
    let matched_new: Vec<usize> = pairs.iter().map(|p| p.1).collect();
    for (index, token) in new.iter().enumerate() {
        assert_eq!(matched_new.contains(&index), token.line != 2, "{token:?}");
    }
    // The line after the insertion keeps its tokens (sliding down a line).
    let print_old = old.iter().position(|t| t.text == "print").unwrap();
    let print_new = new.iter().position(|t| t.text == "print").unwrap();
    assert!(pairs.contains(&(print_old, print_new)));
}

#[test]
fn removed_line_is_unmatched() {
    let old = tokens("a = 1\nb = 2\nc = 3\n");
    let new = tokens("a = 1\nc = 3\n");
    let pairs = match_tokens(&old, &new);
    matched_texts(&old, &new, &pairs);
    assert!(pairs.iter().all(|&(a, _)| old[a].line != 1));
    assert_eq!(pairs.len(), new.len());
}

#[test]
fn renamed_variable_keeps_surrounding_tokens() {
    let old = tokens("def f(count):\n    total = count * 2\n    return total\n");
    let new = tokens("def f(count):\n    result = count * 2\n    return result\n");
    let pairs = match_tokens(&old, &new);
    matched_texts(&old, &new, &pairs);
    let matched_old: Vec<&str> = pairs.iter().map(|&(a, _)| old[a].text.as_str()).collect();
    for kept in ["def", "f", "count", "=", "*", "2", "return"] {
        assert!(
            matched_old.contains(&kept),
            "{kept} should travel: {matched_old:?}"
        );
    }
    assert!(!matched_old.contains(&"total"));
    assert_eq!(pairs.len(), old.len() - 2);
}

#[test]
fn reindented_line_still_matches_whole() {
    let old = tokens("x = 1\n");
    let new = tokens("if ok:\n    x = 1\n");
    let pairs = match_tokens(&old, &new);
    assert_eq!(pairs.len(), old.len());
}

#[test]
fn matching_is_deterministic() {
    let old = tokens("a = b\nb = a\nc = a + b\n");
    let new = tokens("b = a\na = b\nc = b + a\n");
    let first = match_tokens(&old, &new);
    for _ in 0..5 {
        assert_eq!(match_tokens(&old, &new), first);
    }
    assert!(match_tokens(&[], &new).is_empty());
    assert!(match_tokens(&old, &[]).is_empty());
}
