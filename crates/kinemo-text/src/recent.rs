//! A bounded cache that keeps what was used recently: two generations of entries; a hit in
//! the older one moves the entry to the current one, and when the current one is full the
//! older one is dropped. Unlike clearing everything when full, a working set that fits stays
//! cached (animated numbers, counters and typing produce many one-off entries).

use std::collections::HashMap;
use std::hash::Hash;

pub struct RecentCache<K, V> {
    current: HashMap<K, V>,
    previous: HashMap<K, V>,
    /// Entries per generation: the cache holds at most twice this many.
    generation: usize,
}

impl<K: Eq + Hash, V: Clone> RecentCache<K, V> {
    /// A cache holding at most `limit` entries.
    pub fn new(limit: usize) -> Self {
        RecentCache { current: HashMap::new(), previous: HashMap::new(), generation: (limit / 2).max(1) }
    }

    pub fn get(&mut self, key: &K) -> Option<V>
    where
        K: Clone,
    {
        if let Some(value) = self.current.get(key) {
            return Some(value.clone());
        }
        let value = self.previous.remove(key)?;
        self.insert(key.clone(), value.clone());
        Some(value)
    }

    /// Stores `value` unless `key` is already there; returns the stored value.
    pub fn insert(&mut self, key: K, value: V) -> V {
        if !self.current.contains_key(&key) && self.current.len() >= self.generation {
            self.previous = std::mem::take(&mut self.current);
        }
        self.current.entry(key).or_insert(value).clone()
    }

    pub fn len(&self) -> usize {
        self.current.len() + self.previous.len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn recently_used_entries_survive_a_flood_of_new_ones() {
        let mut cache = RecentCache::new(4);
        cache.insert("kept", 0);
        for i in 0..10 {
            assert_eq!(cache.get(&"kept"), Some(0));
            cache.insert(["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"][i], i);
        }
        assert_eq!(cache.get(&"kept"), Some(0));
        assert!(cache.len() <= 4);
    }

    #[test]
    fn stale_entries_are_dropped() {
        let mut cache = RecentCache::new(2);
        cache.insert(1, 1);
        cache.insert(2, 2);
        cache.insert(3, 3);
        assert_eq!(cache.get(&1), None);
        assert_eq!(cache.get(&3), Some(3));
    }
}
