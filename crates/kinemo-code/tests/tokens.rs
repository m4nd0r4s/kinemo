use kinemo_code::{tokenize, CodeError, Token, TokenKind};

fn find<'a>(tokens: &'a [Token], text: &str) -> &'a Token {
    tokens
        .iter()
        .find(|token| token.text == text)
        .unwrap_or_else(|| panic!("no token {text:?} in {tokens:#?}"))
}

#[test]
fn python_tokens() {
    let source = "# compute\ndef area(r):\n    return 3.14 * r * r  # pi r^2\nname = 'circle'\n";
    let tokens = tokenize(source, "python").unwrap();
    assert_eq!(find(&tokens, "def").kind, TokenKind::Keyword);
    assert_eq!(find(&tokens, "return").kind, TokenKind::Keyword);
    assert_eq!(find(&tokens, "area").kind, TokenKind::Function);
    assert_eq!(find(&tokens, "3.14").kind, TokenKind::Number);
    assert_eq!(find(&tokens, "'circle'").kind, TokenKind::String);
    let comment = find(&tokens, "# pi r^2");
    assert_eq!(comment.kind, TokenKind::Comment);
    assert_eq!(comment.line, 2);
    assert_eq!(find(&tokens, "# compute").line, 0);
    // Char ranges point back into the source.
    let chars: Vec<char> = source.chars().collect();
    for token in &tokens {
        let text: String = chars[token.start_char..token.end_char].iter().collect();
        assert_eq!(text, token.text);
        assert!(
            !token.text.starts_with(char::is_whitespace)
                && !token.text.ends_with(char::is_whitespace)
        );
    }
}

#[test]
fn whitespace_is_never_a_token_and_every_other_char_is_covered() {
    let source = "def f(a,\tb):\n\n    return a+b  \n";
    let tokens = tokenize(source, "py").unwrap();
    let mut covered = vec![false; source.chars().count()];
    for token in &tokens {
        assert!(!token.text.trim().is_empty());
        covered[token.start_char..token.end_char].fill(true);
    }
    for (index, character) in source.chars().enumerate() {
        assert_eq!(
            covered[index],
            !character.is_whitespace(),
            "char {index} {character:?}"
        );
    }
}

#[test]
fn rust_tokens() {
    let source =
        "// entry\nfn main() {\n    let total: u32 = 42;\n    println!(\"{}\", total);\n}\n";
    let tokens = tokenize(source, "rust").unwrap();
    assert_eq!(find(&tokens, "fn").kind, TokenKind::Keyword);
    assert_eq!(find(&tokens, "let").kind, TokenKind::Keyword);
    assert_eq!(find(&tokens, "main").kind, TokenKind::Function);
    assert_eq!(find(&tokens, "u32").kind, TokenKind::Type);
    assert_eq!(find(&tokens, "42").kind, TokenKind::Number);
    assert_eq!(find(&tokens, "\"{}\"").kind, TokenKind::String);
    assert_eq!(find(&tokens, "// entry").kind, TokenKind::Comment);
    assert_eq!(find(&tokens, "{").kind, TokenKind::Punctuation);
    assert_eq!(find(&tokens, "=").kind, TokenKind::Operator);
}

#[test]
fn other_languages_tokenize() {
    let samples = [
        ("javascript", "const x = 1; // c", "const"),
        ("typescript", "let n: number = 2;", "number"),
        ("tsx", "const a = <div>{b}</div>;", "const"),
        ("c", "int main(void) { return 0; }", "return"),
        ("cpp", "class A { public: int x; };", "class"),
        ("json", "{\"key\": [1, true]}", "true"),
        ("java", "public class A { int x = 1; }", "class"),
        ("kotlin", "fun main() { val x = 1 }", "fun"),
        ("go", "func main() { return }", "func"),
        ("csharp", "public class A { int x = 1; }", "class"),
        ("swift", "func f() -> Int { return 1 }", "func"),
        ("ruby", "def f\n  return 1\nend", "def"),
        ("haskell", "main = putStrLn \"hi\"", "\"hi\""),
        ("bash", "if true; then echo hi; fi", "if"),
        ("sql", "SELECT name FROM users WHERE id = 1", "SELECT"),
        ("html", "<p class=\"x\">hi</p>", "p"),
        ("css", "p { color: red; }", "color"),
        ("yaml", "name: kinemo\nversion: 1", "1"),
        ("toml", "[tool]\nname = \"kinemo\"", "\"kinemo\""),
    ];
    for (language, source, expected) in samples {
        let tokens = tokenize(source, language).unwrap();
        let token = find(&tokens, expected);
        assert_ne!(token.kind, TokenKind::Plain, "{language}: {token:?}");
    }
    // JSON keys and string values get different colors.
    let json = tokenize("{\"key\": \"value\"}", "json").unwrap();
    assert_eq!(find(&json, "key").kind, TokenKind::Variable);
    assert_eq!(find(&json, "\"value\"").kind, TokenKind::String);
    let sql = tokenize("-- top\nSELECT 1", "sql").unwrap();
    assert_eq!(find(&sql, "-- top").kind, TokenKind::Comment);
    for alias in ["kt", "golang", "c#", "sh", "zsh", "yml", "rb", "hs", "htm"] {
        assert!(tokenize("x", alias).is_ok(), "{alias}");
    }
}

#[test]
fn plain_text_splits_words_and_symbols() {
    let tokens = tokenize("hello, world", "text").unwrap();
    let texts: Vec<&str> = tokens.iter().map(|token| token.text.as_str()).collect();
    assert_eq!(texts, ["hello", ",", "world"]);
    assert!(tokens.iter().all(|token| token.kind == TokenKind::Plain));
}

#[test]
fn unknown_language_is_an_error() {
    let error = tokenize("x", "cobol").unwrap_err();
    assert_eq!(error, CodeError::UnknownLanguage("cobol".to_owned()));
    assert!(error.to_string().contains("python"));
    assert!(kinemo_code::layout_code("x", "cobol", &Default::default()).is_err());
}

#[test]
fn tokenizing_is_deterministic() {
    let source = "fn f(x: i32) -> i32 { x * 2 } // twice";
    let first = tokenize(source, "rust").unwrap();
    for _ in 0..5 {
        assert_eq!(tokenize(source, "rust").unwrap(), first);
    }
    let threads: Vec<_> = (0..4)
        .map(|_| std::thread::spawn(move || tokenize(source, "rust").unwrap()))
        .collect();
    for thread in threads {
        assert_eq!(thread.join().unwrap(), first);
    }
}
