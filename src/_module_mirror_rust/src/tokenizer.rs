use std::collections::HashSet;

lazy_static::lazy_static! {
    static ref PYTHON_KEYWORDS: HashSet<&'static str> = {
        let mut s = HashSet::new();
        for kw in &[
            "False", "None", "True", "and", "as", "assert", "async", "await",
            "break", "class", "continue", "def", "del", "elif", "else", "except",
            "finally", "for", "from", "global", "if", "import", "in", "is",
            "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try",
            "while", "with", "yield",
        ] {
            s.insert(*kw);
        }
        s
    };

    static ref JAVA_KEYWORDS: HashSet<&'static str> = {
        let mut s = HashSet::new();
        for kw in &[
            "abstract", "assert", "boolean", "break", "byte", "case", "catch",
            "char", "class", "const", "continue", "default", "do", "double",
            "else", "enum", "extends", "final", "finally", "float", "for", "goto",
            "if", "implements", "import", "instanceof", "int", "interface", "long",
            "native", "new", "package", "private", "protected", "public", "return",
            "short", "static", "strictfp", "super", "switch", "synchronized",
            "this", "throw", "throws", "transient", "try", "void", "volatile", "while",
        ] {
            s.insert(*kw);
        }
        s
    };

    static ref JS_KEYWORDS: HashSet<&'static str> = {
        let mut s = HashSet::new();
        for kw in &[
            "async", "await", "break", "case", "catch", "class", "const",
            "continue", "debugger", "default", "delete", "do", "else", "export",
            "extends", "false", "finally", "for", "function", "if", "import", "in",
            "instanceof", "let", "new", "null", "of", "return", "static", "super",
            "switch", "this", "throw", "true", "try", "typeof", "undefined", "var",
            "void", "while", "with", "yield",
        ] {
            s.insert(*kw);
        }
        s
    };

    static ref TWO_CHAR_OPS: HashSet<&'static str> = {
        let mut s = HashSet::new();
        for op in &[
            "==", "!=", "<=", ">=", "+=", "-=", "*=", "/=", "//", "**",
            "->", "=>", "<<", ">>", "&&", "||", "++", "--", "??", "?.",
        ] {
            s.insert(*op);
        }
        s
    };
}

fn get_keywords(language: &str) -> &'static HashSet<&'static str> {
    match language {
        "python" => &PYTHON_KEYWORDS,
        "java" => &JAVA_KEYWORDS,
        "javascript" => &JS_KEYWORDS,
        _ => &PYTHON_KEYWORDS,
    }
}

pub fn tokenize_impl(code: String, language: String) -> Vec<String> {
    let keywords = get_keywords(&language);
    let chars: Vec<char> = code.chars().collect();
    let n = chars.len();
    let mut tokens = Vec::new();
    let mut i = 0usize;

    while i < n {
        let c = chars[i];

        if c.is_whitespace() {
            i += 1;
            continue;
        }

        if language == "python" && c == '#' {
            while i < n && chars[i] != '\n' {
                i += 1;
            }
            continue;
        }

        if language == "python" && i + 2 < n {
            let triple = [chars[i], chars[i + 1], chars[i + 2]];
            if triple == ['"', '"', '"'] || triple == ['\'', '\'', '\''] {
                let q0 = chars[i];
                let q1 = chars[i + 1];
                let q2 = chars[i + 2];
                i += 3;
                while i + 2 < n && !(chars[i] == q0 && chars[i + 1] == q1 && chars[i + 2] == q2) {
                    i += 1;
                }
                if i + 2 < n && chars[i] == q0 && chars[i + 1] == q1 && chars[i + 2] == q2 {
                    i += 3;
                }
                continue;
            }
        }

        if (language == "java" || language == "javascript") && i + 1 < n {
            if chars[i] == '/' && chars[i + 1] == '/' {
                while i < n && chars[i] != '\n' {
                    i += 1;
                }
                continue;
            }
            if chars[i] == '/' && chars[i + 1] == '*' {
                i += 2;
                while i + 1 < n && !(chars[i] == '*' && chars[i + 1] == '/') {
                    i += 1;
                }
                if i + 1 < n && chars[i] == '*' && chars[i + 1] == '/' {
                    i += 2;
                }
                continue;
            }
        }

        if c == '"' || c == '\'' {
            let quote = c;
            i += 1;
            while i < n {
                if chars[i] == '\\' && i + 1 < n {
                    i += 2;
                    continue;
                }
                if chars[i] == quote {
                    i += 1;
                    break;
                }
                i += 1;
            }
            tokens.push("STR".to_string());
            continue;
        }

        if c.is_alphabetic() || c == '_' {
            let start = i;
            while i < n && (chars[i].is_alphanumeric() || chars[i] == '_') {
                i += 1;
            }
            let word: String = chars[start..i].iter().collect();
            if keywords.contains(word.as_str()) {
                tokens.push(word);
            } else {
                tokens.push("ID".to_string());
            }
            continue;
        }

        if c.is_ascii_digit() {
            while i < n && (chars[i].is_ascii_digit() || chars[i] == '.') {
                i += 1;
            }
            tokens.push("NUM".to_string());
            continue;
        }

        if i + 1 < n {
            let two: String = chars[i..i + 2].iter().collect();
            if TWO_CHAR_OPS.contains(two.as_str()) {
                tokens.push(two);
                i += 2;
                continue;
            }
        }

        tokens.push(c.to_string());
        i += 1;
    }

    tokens
}
