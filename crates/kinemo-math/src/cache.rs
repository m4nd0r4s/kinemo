//! Global, bounded layout cache keyed by (TeX, options). Errors are cached too,
//! so a broken formula is not recompiled on every frame.

use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};

use crate::error::MathError;
use crate::types::{MathLayout, MathOptions};

#[derive(Clone, PartialEq, Eq, Hash)]
struct CacheKey {
    tex: String,
    size: u64,
    display: bool,
}

/// The cache is cleared when it reaches this many entries.
const CACHE_LIMIT: usize = 2048;

type CachedResult = Result<Arc<MathLayout>, MathError>;
type Cache = Mutex<HashMap<CacheKey, CachedResult>>;

fn cache() -> &'static Cache {
    static CACHE: OnceLock<Cache> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

/// Lay out a LaTeX math formula (no `$` delimiters) into glyph outlines.
///
/// The result is cached; identical calls return the same `Arc`.
pub fn layout_math(tex: &str, opts: &MathOptions) -> Result<Arc<MathLayout>, MathError> {
    let key = CacheKey { tex: tex.to_owned(), size: opts.size.to_bits(), display: opts.display };
    if let Some(hit) = cache().lock().unwrap_or_else(|e| e.into_inner()).get(&key) {
        return hit.clone();
    }
    // Computed outside the lock; a concurrent duplicate computation is harmless
    // because layout is deterministic.
    let result = crate::pipeline::compute(tex, opts).map(Arc::new);
    let mut c = cache().lock().unwrap_or_else(|e| e.into_inner());
    if c.len() >= CACHE_LIMIT {
        c.clear();
    }
    c.entry(key).or_insert(result).clone()
}
