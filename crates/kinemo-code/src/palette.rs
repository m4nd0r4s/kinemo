//! Color palettes for token kinds (RGBA, components in 0..=1).

use crate::tokens::TokenKind;

pub type Color = [f64; 4];

#[derive(Clone, Debug, PartialEq)]
pub struct Palette {
    pub keyword: Color,
    pub function: Color,
    pub type_name: Color,
    pub string: Color,
    pub number: Color,
    pub comment: Color,
    pub operator: Color,
    pub punctuation: Color,
    pub variable: Color,
    pub constant: Color,
    pub plain: Color,
    /// Suggested panel background.
    pub background: Color,
    /// Gutter line numbers.
    pub line_number: Color,
    /// Background tint for highlighted lines.
    pub line_highlight: Color,
}

const fn hex(rgb: u32) -> Color {
    [
        ((rgb >> 16) & 0xff) as f64 / 255.0,
        ((rgb >> 8) & 0xff) as f64 / 255.0,
        (rgb & 0xff) as f64 / 255.0,
        1.0,
    ]
}

impl Palette {
    /// Dark theme (One Dark inspired).
    pub fn dark() -> Palette {
        Palette {
            keyword: hex(0xc678dd),
            function: hex(0x61afef),
            type_name: hex(0xe5c07b),
            string: hex(0x98c379),
            number: hex(0xd19a66),
            comment: hex(0x7f848e),
            operator: hex(0x56b6c2),
            punctuation: hex(0xabb2bf),
            variable: hex(0xe06c75),
            constant: hex(0xd19a66),
            plain: hex(0xdcdfe4),
            background: hex(0x282c34),
            line_number: hex(0x636d83),
            line_highlight: [1.0, 1.0, 1.0, 0.08],
        }
    }

    /// Light theme (One Light inspired).
    pub fn light() -> Palette {
        Palette {
            keyword: hex(0xa626a4),
            function: hex(0x4078f2),
            type_name: hex(0xc18401),
            string: hex(0x50a14f),
            number: hex(0x986801),
            comment: hex(0xa0a1a7),
            operator: hex(0x0184bc),
            punctuation: hex(0x383a42),
            variable: hex(0xe45649),
            constant: hex(0x986801),
            plain: hex(0x383a42),
            background: hex(0xfafafa),
            line_number: hex(0x9d9d9f),
            line_highlight: [0.0, 0.0, 0.0, 0.06],
        }
    }

    pub fn color(&self, kind: TokenKind) -> Color {
        match kind {
            TokenKind::Keyword => self.keyword,
            TokenKind::Function => self.function,
            TokenKind::Type => self.type_name,
            TokenKind::String => self.string,
            TokenKind::Number => self.number,
            TokenKind::Comment => self.comment,
            TokenKind::Operator => self.operator,
            TokenKind::Punctuation => self.punctuation,
            TokenKind::Variable => self.variable,
            TokenKind::Constant => self.constant,
            TokenKind::Plain => self.plain,
        }
    }
}

impl Default for Palette {
    fn default() -> Palette {
        Palette::dark()
    }
}
