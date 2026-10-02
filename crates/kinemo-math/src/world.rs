//! A minimal typst `World`: one in-memory source file and the fonts embedded in
//! `typst-assets` (New Computer Modern, New Computer Modern Math, ...). There is
//! no filesystem, package or network access, and no clock, so compilation is
//! deterministic.

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::LazyLock;

use typst::diag::{FileError, FileResult};
use typst::foundations::{Bytes, Datetime, Duration};
use typst::layout::Frame;
use typst::syntax::{FileId, RootedPath, Source, VirtualPath, VirtualRoot};
use typst::text::{Font, FontBook};
use typst::utils::LazyHash;
use typst::{Library, LibraryExt, World};
use typst_layout::PagedDocument;

static FONTS: LazyLock<Vec<Font>> =
    LazyLock::new(|| typst_assets::fonts().flat_map(|data| Font::iter(Bytes::new(data))).collect());

static BOOK: LazyLock<LazyHash<FontBook>> = LazyLock::new(|| LazyHash::new(FontBook::from_fonts(FONTS.iter())));

static LIBRARY: LazyLock<LazyHash<Library>> = LazyLock::new(|| LazyHash::new(Library::default()));

static MAIN_ID: LazyLock<FileId> = LazyLock::new(|| {
    let path = VirtualPath::new("main.typ").expect("valid virtual path");
    FileId::new(RootedPath::new(VirtualRoot::Project, path))
});

/// Compilations between two evictions of typst's memoization caches.
const EVICT_EVERY: usize = 64;
/// Cache entries unused for this many evictions are dropped.
const EVICT_MAX_AGE: usize = 8;

static COMPILATIONS: AtomicUsize = AtomicUsize::new(0);

struct MathWorld {
    source: Source,
}

impl World for MathWorld {
    fn library(&self) -> &LazyHash<Library> {
        &LIBRARY
    }

    fn book(&self) -> &LazyHash<FontBook> {
        &BOOK
    }

    fn main(&self) -> FileId {
        *MAIN_ID
    }

    fn source(&self, id: FileId) -> FileResult<Source> {
        if id == *MAIN_ID {
            Ok(self.source.clone())
        } else {
            Err(FileError::AccessDenied)
        }
    }

    fn file(&self, _id: FileId) -> FileResult<Bytes> {
        Err(FileError::AccessDenied)
    }

    fn font(&self, index: usize) -> Option<Font> {
        FONTS.get(index).cloned()
    }

    fn today(&self, _offset: Option<Duration>) -> Option<Datetime> {
        None
    }
}

/// Compile a typst document and return the frame of its first page.
pub(crate) fn compile_first_page(document: &str) -> Result<Frame, String> {
    let world = MathWorld { source: Source::new(*MAIN_ID, document.to_owned()) };
    let result = typst::compile::<PagedDocument>(&world).output;

    if COMPILATIONS.fetch_add(1, Ordering::Relaxed) % EVICT_EVERY == EVICT_EVERY - 1 {
        comemo::evict(EVICT_MAX_AGE);
    }

    match result {
        Ok(doc) => doc.pages().first().map(|p| p.frame.clone()).ok_or_else(|| "empty document".to_owned()),
        Err(diagnostics) => {
            let messages: Vec<String> = diagnostics.iter().map(|d| d.message.to_string()).collect();
            Err(messages.join("; "))
        }
    }
}
