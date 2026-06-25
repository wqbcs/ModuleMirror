use pyo3::prelude::*;

use gaoya::minhash::{MinHashIndex, MinHasher, MinHasher32};
use std::collections::HashMap;

#[pyclass]
pub struct PyMinHashLSH {
    num_bands: usize,
    band_width: usize,
    num_perm: usize,
    jaccard_threshold: f64,
    index: MinHashIndex<u32, String>,
    hasher: MinHasher32<ahash::RandomState>,
    module_signatures: HashMap<String, Vec<u32>>,
}

#[pymethods]
impl PyMinHashLSH {
    #[new]
    #[pyo3(signature = (num_perm=128, jaccard_threshold=0.5, num_bands=None))]
    fn new(num_perm: usize, jaccard_threshold: f64, num_bands: Option<usize>) -> Self {
        let bands = match num_bands {
            Some(b) => b,
            None => {
                let raw = (num_perm as f64 / (1.0 / jaccard_threshold).ln()).ceil() as usize;
                let b = raw.max(1).min(num_perm);
                let b = (num_perm / (num_perm / b)).max(1);
                b
            }
        };
        let band_width = num_perm / bands;
        let actual_num_perm = bands * band_width;

        let index = MinHashIndex::new(bands, band_width, jaccard_threshold);
        let build_hasher = ahash::RandomState::with_seeds(42, 43, 44, 45);
        let hasher = MinHasher32::new_with_hasher(actual_num_perm, build_hasher);

        Self {
            num_bands: bands,
            band_width,
            num_perm: actual_num_perm,
            jaccard_threshold,
            index,
            hasher,
            module_signatures: HashMap::new(),
        }
    }

    fn insert(&mut self, module_id: String, tokens: Vec<String>) {
        if self.module_signatures.contains_key(&module_id) {
            self.index.remove(&module_id);
        }

        let signature = self.hasher.create_signature(tokens.iter().map(|s| s.as_str()));
        self.module_signatures.insert(module_id.clone(), signature.clone());
        self.index.insert(module_id, signature);
    }

    fn insert_signature(&mut self, module_id: String, signature: Vec<u32>) {
        if self.module_signatures.contains_key(&module_id) {
            self.index.remove(&module_id);
        }

        self.module_signatures.insert(module_id.clone(), signature.clone());
        self.index.insert(module_id, signature);
    }

    fn query_by_tokens(&self, tokens: Vec<String>, top_k: Option<usize>) -> Vec<(String, f64)> {
        let signature = self.hasher.create_signature(tokens.iter().map(|s| s.as_str()));
        self._query_signature(&signature, top_k)
    }

    fn query_by_signature(&self, signature: Vec<u32>, top_k: Option<usize>) -> Vec<(String, f64)> {
        self._query_signature(&signature, top_k)
    }

    fn query_by_module(&self, module_id: String, top_k: Option<usize>) -> Vec<(String, f64)> {
        if let Some(sig) = self.module_signatures.get(&module_id) {
            let mut results = self._query_signature(sig, top_k);
            results.retain(|(id, _)| id != &module_id);
            results
        } else {
            Vec::new()
        }
    }

    fn remove(&mut self, module_id: String) {
        self.index.remove(&module_id);
        self.module_signatures.remove(&module_id);
    }

    fn get_signature(&self, module_id: String) -> Option<Vec<u32>> {
        self.module_signatures.get(&module_id).cloned()
    }

    fn estimate_jaccard(&self, module_id1: String, module_id2: String) -> Option<f64> {
        let sig1 = self.module_signatures.get(&module_id1)?;
        let sig2 = self.module_signatures.get(&module_id2)?;
        let matches = sig1.iter().zip(sig2.iter()).filter(|(a, b)| a == b).count();
        Some(matches as f64 / sig1.len() as f64)
    }

    #[getter]
    fn module_count(&self) -> usize {
        self.module_signatures.len()
    }

    #[getter]
    fn num_bands(&self) -> usize {
        self.num_bands
    }

    #[getter]
    fn band_width(&self) -> usize {
        self.band_width
    }
}

impl PyMinHashLSH {
    fn _query_signature(&self, signature: &Vec<u32>, top_k: Option<usize>) -> Vec<(String, f64)> {
        let candidates = self.index.query_owned(signature);

        let mut results: Vec<(String, f64)> = candidates
            .into_iter()
            .filter_map(|module_id| {
                let other_sig = self.module_signatures.get(&module_id)?;
                let matches = signature
                    .iter()
                    .zip(other_sig.iter())
                    .filter(|(a, b)| a == b)
                    .count();
                let jaccard = matches as f64 / signature.len() as f64;
                Some((module_id, jaccard))
            })
            .filter(|(_, jaccard)| *jaccard >= self.jaccard_threshold)
            .collect();

        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        if let Some(k) = top_k {
            results.truncate(k);
        }

        results
    }
}
