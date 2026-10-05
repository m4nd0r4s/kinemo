//! Global, bounded cache of code layouts keyed by (source, language, options).

use std::sync::{Arc, Mutex, OnceLock};

use kinemo_text::recent::RecentCache;

use crate::languages::{resolve, Language};
use crate::layout::{compute_layout, CodeLayout, CodeOptions};
use crate::CodeError;

#[derive(Clone, PartialEq, Eq, Hash)]
struct CacheKey {
    source: String,
    language: Language,
    size: u64,
    line_height: u64,
    tab_width: usize,
    line_numbers: bool,
}

/// Layouts kept (the most recently used survive).
const CACHE_LIMIT: usize = 512;

type Cache = Mutex<RecentCache<CacheKey, Arc<CodeLayout>>>;

fn cache() -> &'static Cache {
    static CACHE: OnceLock<Cache> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(RecentCache::new(CACHE_LIMIT)))
}

/// Lay out highlighted code. The block is centered at (0,0), y-up. Cached.
pub fn layout_code(
    source: &str,
    language: &str,
    options: &CodeOptions,
) -> Result<Arc<CodeLayout>, CodeError> {
    let language = resolve(language)?;
    let key = CacheKey {
        source: source.to_owned(),
        language,
        size: options.size.to_bits(),
        line_height: options.line_height.to_bits(),
        tab_width: options.tab_width,
        line_numbers: options.line_numbers,
    };
    if let Some(layout) = cache()
        .lock()
        .unwrap_or_else(|error| error.into_inner())
        .get(&key)
    {
        return Ok(layout);
    }
    // Computed outside the lock; layout is deterministic, so a concurrent
    // duplicate computation is harmless.
    let layout = Arc::new(compute_layout(source, language, options)?);
    Ok(cache().lock().unwrap_or_else(|error| error.into_inner()).insert(key, layout))
}
