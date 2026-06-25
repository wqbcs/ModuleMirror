use pyo3::prelude::*;

use gaoya::minhash::{MinHasher, MinHasher32};

#[pyclass]
pub struct PyMinHash {
    num_perm: usize,
    hasher: MinHasher32<ahash::RandomState>,
    signature: Vec<u32>,
}

#[pymethods]
impl PyMinHash {
    #[new]
    #[pyo3(signature = (num_perm=128, seed=None))]
    fn new(num_perm: usize, seed: Option<u64>) -> Self {
        let build_hasher = ahash::RandomState::with_seeds(
            seed.unwrap_or(42),
            seed.unwrap_or(42).wrapping_add(1),
            seed.unwrap_or(42).wrapping_add(2),
            seed.unwrap_or(42).wrapping_add(3),
        );
        let hasher = MinHasher32::new_with_hasher(num_perm, build_hasher);
        let signature = vec![u32::MAX; num_perm];
        Self {
            num_perm,
            hasher,
            signature,
        }
    }

    fn update_batch(&mut self, tokens: Vec<String>) {
        let sig = self.hasher.create_signature(tokens.iter().map(|s| s.as_str()));
        for i in 0..self.num_perm {
            if sig[i] < self.signature[i] {
                self.signature[i] = sig[i];
            }
        }
    }

    fn update(&mut self, token: String) {
        let sig = self.hasher.create_signature(std::iter::once(token.as_str()));
        for i in 0..self.num_perm {
            if sig[i] < self.signature[i] {
                self.signature[i] = sig[i];
            }
        }
    }

    fn jaccard(&self, other: &PyMinHash) -> PyResult<f64> {
        if self.num_perm != other.num_perm {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "MinHash signatures must have the same num_perm",
            ));
        }
        let mut matches = 0u64;
        for i in 0..self.num_perm {
            if self.signature[i] == other.signature[i] {
                matches += 1;
            }
        }
        Ok(matches as f64 / self.num_perm as f64)
    }

    fn get_signature(&self) -> Vec<u32> {
        self.signature.clone()
    }

    fn merge(&mut self, other: &PyMinHash) -> PyResult<()> {
        if self.num_perm != other.num_perm {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "MinHash signatures must have the same num_perm",
            ));
        }
        for i in 0..self.num_perm {
            if other.signature[i] < self.signature[i] {
                self.signature[i] = other.signature[i];
            }
        }
        Ok(())
    }

    #[getter]
    fn num_perm(&self) -> usize {
        self.num_perm
    }
}

pub fn create_minhash_signature(tokens: Vec<String>, num_perm: usize) -> Vec<u32> {
    let hasher = MinHasher32::new(num_perm);
    hasher.create_signature(tokens.iter().map(|s| s.as_str()))
}

pub fn create_minhash_signatures_batch(items: Vec<Vec<String>>, num_perm: usize) -> Vec<Vec<u32>> {
    let hasher = MinHasher32::new(num_perm);
    items
        .iter()
        .map(|tokens| hasher.create_signature(tokens.iter().map(|s| s.as_str())))
        .collect()
}

pub fn create_minhash_signatures_parallel(items: Vec<Vec<String>>, num_perm: usize) -> Vec<Vec<u32>> {
    use rayon::prelude::*;
    let hasher = MinHasher32::new(num_perm);
    items
        .par_iter()
        .map(|tokens| hasher.create_signature(tokens.iter().map(|s| s.as_str())))
        .collect()
}

pub fn estimate_jaccard_impl(sig1: &[u32], sig2: &[u32]) -> f64 {
    let matches = sig1.iter().zip(sig2.iter()).filter(|(a, b)| a == b).count();
    matches as f64 / sig1.len() as f64
}
