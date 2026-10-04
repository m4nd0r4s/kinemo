//! Supported languages, their aliases and their tree-sitter grammars/queries.

use tree_sitter::Language as Grammar;

/// A supported language. `PlainText` has no grammar: every token is `Plain`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Language {
    Python,
    Rust,
    JavaScript,
    TypeScript,
    Tsx,
    C,
    Cpp,
    Json,
    Java,
    Kotlin,
    Go,
    CSharp,
    Swift,
    Ruby,
    Haskell,
    Bash,
    Sql,
    Html,
    Css,
    Yaml,
    Toml,
    PlainText,
}

impl Language {
    pub const ALL: [Language; 22] = [
        Language::Python,
        Language::Rust,
        Language::JavaScript,
        Language::TypeScript,
        Language::Tsx,
        Language::C,
        Language::Cpp,
        Language::Json,
        Language::Java,
        Language::Kotlin,
        Language::Go,
        Language::CSharp,
        Language::Swift,
        Language::Ruby,
        Language::Haskell,
        Language::Bash,
        Language::Sql,
        Language::Html,
        Language::Css,
        Language::Yaml,
        Language::Toml,
        Language::PlainText,
    ];

    /// Canonical lowercase name.
    pub fn name(self) -> &'static str {
        match self {
            Language::Python => "python",
            Language::Rust => "rust",
            Language::JavaScript => "javascript",
            Language::TypeScript => "typescript",
            Language::Tsx => "tsx",
            Language::C => "c",
            Language::Cpp => "cpp",
            Language::Json => "json",
            Language::Java => "java",
            Language::Kotlin => "kotlin",
            Language::Go => "go",
            Language::CSharp => "csharp",
            Language::Swift => "swift",
            Language::Ruby => "ruby",
            Language::Haskell => "haskell",
            Language::Bash => "bash",
            Language::Sql => "sql",
            Language::Html => "html",
            Language::Css => "css",
            Language::Yaml => "yaml",
            Language::Toml => "toml",
            Language::PlainText => "text",
        }
    }

    /// Resolve a name or alias (case-insensitive), e.g. `"py"`, `"C++"`, `"ts"`.
    pub fn from_name(name: &str) -> Option<Language> {
        let lowered = name.trim().to_ascii_lowercase();
        let language = match lowered.as_str() {
            "python" | "py" | "python3" => Language::Python,
            "rust" | "rs" => Language::Rust,
            "javascript" | "js" | "jsx" | "mjs" | "cjs" => Language::JavaScript,
            "typescript" | "ts" | "mts" | "cts" => Language::TypeScript,
            "tsx" => Language::Tsx,
            "c" | "h" => Language::C,
            "cpp" | "c++" | "cc" | "cxx" | "hpp" | "hh" | "hxx" => Language::Cpp,
            "json" => Language::Json,
            "java" => Language::Java,
            "kotlin" | "kt" | "kts" => Language::Kotlin,
            "go" | "golang" => Language::Go,
            "csharp" | "c#" | "cs" => Language::CSharp,
            "swift" => Language::Swift,
            "ruby" | "rb" => Language::Ruby,
            "haskell" | "hs" => Language::Haskell,
            "bash" | "sh" | "shell" | "zsh" | "console" => Language::Bash,
            "sql" => Language::Sql,
            "html" | "htm" => Language::Html,
            "css" => Language::Css,
            "yaml" | "yml" => Language::Yaml,
            "toml" => Language::Toml,
            "text" | "plain" | "txt" | "plaintext" | "none" | "" => Language::PlainText,
            _ => return None,
        };
        Some(language)
    }

    /// The tree-sitter grammar, or `None` for plain text.
    pub(crate) fn grammar(self) -> Option<Grammar> {
        let grammar = match self {
            Language::Python => tree_sitter_python::LANGUAGE,
            Language::Rust => tree_sitter_rust::LANGUAGE,
            Language::JavaScript => tree_sitter_javascript::LANGUAGE,
            Language::TypeScript => tree_sitter_typescript::LANGUAGE_TYPESCRIPT,
            Language::Tsx => tree_sitter_typescript::LANGUAGE_TSX,
            Language::C => tree_sitter_c::LANGUAGE,
            Language::Cpp => tree_sitter_cpp::LANGUAGE,
            Language::Json => tree_sitter_json::LANGUAGE,
            Language::Java => tree_sitter_java::LANGUAGE,
            Language::Kotlin => tree_sitter_kotlin_ng::LANGUAGE,
            Language::Go => tree_sitter_go::LANGUAGE,
            Language::CSharp => tree_sitter_c_sharp::LANGUAGE,
            Language::Swift => tree_sitter_swift::LANGUAGE,
            Language::Ruby => tree_sitter_ruby::LANGUAGE,
            Language::Haskell => tree_sitter_haskell::LANGUAGE,
            Language::Bash => tree_sitter_bash::LANGUAGE,
            Language::Sql => tree_sitter_sequel::LANGUAGE,
            Language::Html => tree_sitter_html::LANGUAGE,
            Language::Css => tree_sitter_css::LANGUAGE,
            Language::Yaml => tree_sitter_yaml::LANGUAGE,
            Language::Toml => tree_sitter_toml_ng::LANGUAGE,
            Language::PlainText => return None,
        };
        Some(grammar.into())
    }

    /// Highlight query. Derived grammars (TypeScript, C++) inherit the base
    /// grammar's query, which is prepended, like the tree-sitter CLI does.
    pub(crate) fn highlights_query(self) -> String {
        match self {
            Language::Python => tree_sitter_python::HIGHLIGHTS_QUERY.to_owned(),
            Language::Rust => tree_sitter_rust::HIGHLIGHTS_QUERY.to_owned(),
            Language::JavaScript => [
                tree_sitter_javascript::HIGHLIGHT_QUERY,
                tree_sitter_javascript::JSX_HIGHLIGHT_QUERY,
            ]
            .join("\n"),
            Language::TypeScript => [
                tree_sitter_javascript::HIGHLIGHT_QUERY,
                tree_sitter_typescript::HIGHLIGHTS_QUERY,
            ]
            .join("\n"),
            Language::Tsx => [
                tree_sitter_javascript::HIGHLIGHT_QUERY,
                tree_sitter_javascript::JSX_HIGHLIGHT_QUERY,
                tree_sitter_typescript::HIGHLIGHTS_QUERY,
            ]
            .join("\n"),
            Language::C => tree_sitter_c::HIGHLIGHT_QUERY.to_owned(),
            Language::Cpp => [
                tree_sitter_c::HIGHLIGHT_QUERY,
                tree_sitter_cpp::HIGHLIGHT_QUERY,
            ]
            .join("\n"),
            // Keys after strings: the last pattern that captures a node wins.
            Language::Json => [tree_sitter_json::HIGHLIGHTS_QUERY, "(pair key: (string) @property)"].join("\n"),
            Language::Java => tree_sitter_java::HIGHLIGHTS_QUERY.to_owned(),
            Language::Kotlin => include_str!("../queries/kotlin.scm").to_owned(),
            Language::Go => tree_sitter_go::HIGHLIGHTS_QUERY.to_owned(),
            Language::CSharp => tree_sitter_c_sharp::HIGHLIGHTS_QUERY.to_owned(),
            Language::Swift => tree_sitter_swift::HIGHLIGHTS_QUERY.to_owned(),
            Language::Ruby => tree_sitter_ruby::HIGHLIGHTS_QUERY.to_owned(),
            Language::Haskell => tree_sitter_haskell::HIGHLIGHTS_QUERY.to_owned(),
            Language::Bash => tree_sitter_bash::HIGHLIGHT_QUERY.to_owned(),
            // `(comment) @comment @spell` keeps neither capture: comments are restated.
            Language::Sql => [tree_sitter_sequel::HIGHLIGHTS_QUERY, "(comment) @comment"].join("\n"),
            Language::Html => tree_sitter_html::HIGHLIGHTS_QUERY.to_owned(),
            Language::Css => tree_sitter_css::HIGHLIGHTS_QUERY.to_owned(),
            Language::Yaml => tree_sitter_yaml::HIGHLIGHTS_QUERY.to_owned(),
            Language::Toml => tree_sitter_toml_ng::HIGHLIGHTS_QUERY.to_owned(),
            Language::PlainText => String::new(),
        }
    }

    /// Locals query (scope-aware variable highlighting), where the grammar ships one.
    pub(crate) fn locals_query(self) -> String {
        match self {
            Language::JavaScript => tree_sitter_javascript::LOCALS_QUERY.to_owned(),
            Language::TypeScript | Language::Tsx => [
                tree_sitter_javascript::LOCALS_QUERY,
                tree_sitter_typescript::LOCALS_QUERY,
            ]
            .join("\n"),
            _ => String::new(),
        }
    }
}

/// Canonical names of every supported language.
pub fn supported_languages() -> Vec<&'static str> {
    Language::ALL
        .iter()
        .map(|language| language.name())
        .collect()
}

/// Resolve a language name, or fail with `CodeError::UnknownLanguage`.
pub(crate) fn resolve(name: &str) -> Result<Language, crate::CodeError> {
    Language::from_name(name).ok_or_else(|| crate::CodeError::UnknownLanguage(name.to_owned()))
}
