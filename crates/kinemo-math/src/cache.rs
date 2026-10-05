//! Global, bounded layout cache keyed by (TeX, options). Errors are cached too,
//! so a broken formula is not recompiled on every frame.

use std::sync::{Arc, Mutex, OnceLock};

use kinemo_text::recent::RecentCache;

use crate::error::MathError;
use crate::types::{MathLayout, MathOptions};

#[derive(Clone, PartialEq, Eq, Hash)]
struct CacheKey {
    tex: String,
    size: u64,
    display: bool,
}

/// Layouts kept (the most recently used survive).
const CACHE_LIMIT: usize = 2048;

type CachedResult = Result<Arc<MathLayout>, MathError>;
type Cache = Mutex<RecentCache<CacheKey, CachedResult>>;

fn cache() -> &'static Cache {
    static CACHE: OnceLock<Cache> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(RecentCache::new(CACHE_LIMIT)))
}

/// Lay out a LaTeX math formula (no `$` delimiters) into glyph outlines.
///
/// The result is cached; identical calls return the same `Arc`.
pub fn layout_math(tex: &str, opts: &MathOptions) -> Result<Arc<MathLayout>, MathError> {
    let key = CacheKey { tex: tex.to_owned(), size: opts.size.to_bits(), display: opts.display };
    if let Some(hit) = cache().lock().unwrap_or_else(|e| e.into_inner()).get(&key) {
        return hit;
    }
    // Computed outside the lock; a concurrent duplicate computation is harmless
    // because layout is deterministic.
    let result = crate::pipeline::compute(tex, opts).map(Arc::new);
    cache().lock().unwrap_or_else(|e| e.into_inner()).insert(key, result)
}
