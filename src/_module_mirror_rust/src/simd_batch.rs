use pyo3::prelude::*;
use rayon::prelude::*;
use std::collections::{HashMap, HashSet};

fn sorted_intersection_count(a: &[i64], b: &[i64]) -> usize {
    let mut count = 0usize;
    let mut i = 0usize;
    let mut j = 0usize;
    while i < a.len() && j < b.len() {
        if a[i] == b[j] {
            count += 1;
            i += 1;
            j += 1;
        } else if a[i] < b[j] {
            i += 1;
        } else {
            j += 1;
        }
    }
    count
}

fn sorted_jaccard(a: &[i64], b: &[i64]) -> f64 {
    if a.is_empty() && b.is_empty() {
        return 100.0;
    }
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }
    let intersection = sorted_intersection_count(a, b);
    let union = a.len() + b.len() - intersection;
    if union == 0 {
        return 100.0;
    }
    (intersection as f64 / union as f64) * 100.0
}

pub fn jaccard_sorted_impl(set1: Vec<i64>, set2: Vec<i64>) -> f64 {
    let mut a = set1;
    let mut b = set2;
    a.sort_unstable();
    b.sort_unstable();
    a.dedup();
    b.dedup();
    sorted_jaccard(&a, &b)
}

pub fn jaccard_sorted_many_impl(
    query: Vec<i64>,
    candidates: Vec<Vec<i64>>,
) -> Vec<f64> {
    let mut q = query;
    q.sort_unstable();
    q.dedup();
    candidates
        .iter()
        .map(|c| {
            let mut b = c.clone();
            b.sort_unstable();
            b.dedup();
            sorted_jaccard(&q, &b)
        })
        .collect()
}

pub fn jaccard_sorted_many_parallel_impl(
    query: Vec<i64>,
    candidates: Vec<Vec<i64>>,
) -> Vec<f64> {
    let mut q = query;
    q.sort_unstable();
    q.dedup();
    candidates
        .par_iter()
        .map(|c| {
            let mut b = c.clone();
            b.sort_unstable();
            b.dedup();
            sorted_jaccard(&q, &b)
        })
        .collect()
}

pub fn intersection_sorted_impl(set1: Vec<i64>, set2: Vec<i64>) -> Vec<i64> {
    let mut a = set1;
    let mut b = set2;
    a.sort_unstable();
    b.sort_unstable();
    a.dedup();
    b.dedup();
    let mut result = Vec::new();
    let mut i = 0usize;
    let mut j = 0usize;
    while i < a.len() && j < b.len() {
        if a[i] == b[j] {
            result.push(a[i]);
            i += 1;
            j += 1;
        } else if a[i] < b[j] {
            i += 1;
        } else {
            j += 1;
        }
    }
    result
}

pub fn find_duplicates_impl(
    hash_array: Vec<i64>,
    module_ids: Vec<i32>,
) -> HashMap<i32, Vec<i32>> {
    if hash_array.is_empty() {
        return HashMap::new();
    }

    let mut indices: Vec<usize> = (0..hash_array.len()).collect();
    indices.sort_by_key(|&i| hash_array[i]);

    let mut duplicates: HashMap<i32, Vec<i32>> = HashMap::new();

    let mut i = 0;
    while i < indices.len() {
        let current_hash = hash_array[indices[i]];
        let mut group = vec![module_ids[indices[i]]];

        let mut j = i + 1;
        while j < indices.len() && hash_array[indices[j]] == current_hash {
            group.push(module_ids[indices[j]]);
            j += 1;
        }

        if group.len() > 1 {
            let unique_ids: HashSet<i32> = group.into_iter().collect();
            let id_vec: Vec<i32> = unique_ids.iter().copied().collect();
            for &mid in &id_vec {
                let others: Vec<i32> = id_vec
                    .iter()
                    .copied()
                    .filter(|&o| o != mid)
                    .collect();
                if !others.is_empty() {
                    duplicates.entry(mid).or_default().extend(others);
                }
            }
        }

        i = j;
    }

    for vals in duplicates.values_mut() {
        vals.sort_unstable();
        vals.dedup();
    }

    duplicates
}

#[pyclass]
pub struct PyInvertedIndex {
    index: HashMap<i64, Vec<String>>,
    module_fingerprints: HashMap<String, HashSet<i64>>,
}

#[pymethods]
impl PyInvertedIndex {
    #[new]
    fn new() -> Self {
        Self {
            index: HashMap::new(),
            module_fingerprints: HashMap::new(),
        }
    }

    fn add_module(&mut self, module_id: String, fingerprints: Vec<i64>) {
        if self.module_fingerprints.contains_key(&module_id) {
            self.remove_module(module_id.clone());
        }

        let fp_set: HashSet<i64> = fingerprints.into_iter().collect();
        for &fp in &fp_set {
            self.index.entry(fp).or_default().push(module_id.clone());
        }
        self.module_fingerprints.insert(module_id, fp_set);
    }

    fn remove_module(&mut self, module_id: String) {
        if let Some(old_fps) = self.module_fingerprints.remove(&module_id) {
            for fp in old_fps {
                if let Some(modules) = self.index.get_mut(&fp) {
                    modules.retain(|m| m != &module_id);
                    if modules.is_empty() {
                        self.index.remove(&fp);
                    }
                }
            }
        }
    }

    fn get_candidates(&self, fingerprints: Vec<i64>) -> HashMap<String, i32> {
        let mut candidate_counts: HashMap<String, i32> = HashMap::new();
        for &fp in &fingerprints {
            if let Some(modules) = self.index.get(&fp) {
                for mid in modules {
                    *candidate_counts.entry(mid.clone()).or_insert(0) += 1;
                }
            }
        }
        candidate_counts
    }

    fn lookup(&self, fingerprint: i64) -> Vec<String> {
        self.index.get(&fingerprint).cloned().unwrap_or_default()
    }

    fn get_module_count(&self) -> usize {
        self.module_fingerprints.len()
    }

    fn get_index_size(&self) -> usize {
        self.index.len()
    }
}
