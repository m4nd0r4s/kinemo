; Kotlin highlights for tree-sitter-kotlin-ng, which ships no queries. Written for kinemo
; from the grammar's node types; captures follow the names in `highlight.rs`.

[
  "abstract" "actual" "annotation" "as" "by" "catch" "class" "companion" "const"
  "constructor" "crossinline" "data" "do" "else" "enum" "expect" "external" "final"
  "finally" "for" "fun" "get" "if" "import" "in" "infix" "init" "inline" "inner"
  "interface" "internal" "is" "lateinit" "noinline" "object" "open" "operator" "out"
  "override" "package" "private" "protected" "public" "return" "sealed" "set" "super"
  "suspend" "tailrec" "this" "throw" "try" "typealias" "val" "value" "var" "vararg"
  "when" "where" "while"
] @keyword

[(line_comment) (block_comment) (shebang)] @comment

[(string_literal) (multiline_string_literal) (character_literal)] @string
(escape_sequence) @escape
(interpolation) @embedded

[(number_literal) (float_literal)] @number

(user_type (identifier) @type)
(class_declaration name: (identifier) @type)
(object_declaration name: (identifier) @type)

(function_declaration name: (identifier) @function)
(call_expression (identifier) @function)
(call_expression (navigation_expression (identifier) @function .))

(annotation) @attribute
(label) @label

(parameter (identifier) @variable)
