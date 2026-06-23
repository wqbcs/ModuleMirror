use pyo3::prelude::*;

const DEFAULT_BASE: u64 = 257;
const DEFAULT_MODULUS: u64 = 2_147_483_647;

#[pyclass]
pub struct PyRollingHash {
    base: u64,
    modulus: u64,
}

#[pymethods]
impl PyRollingHash {
    #[new]
    #[pyo3(signature = (base=None, modulus=None))]
    fn new(base: Option<u64>, modulus: Option<u64>) -> Self {
        Self {
            base: base.unwrap_or(DEFAULT_BASE),
            modulus: modulus.unwrap_or(DEFAULT_MODULUS),
        }
    }

    fn hash_sequence(&self, tokens: Vec<String>, seed: u32) -> u64 {
        use murmur3::murmur3_32;
        use std::io::Cursor;
        let mut hash_value: u64 = 0;
        for token in &tokens {
            let token_hash = murmur3_32(&mut Cursor::new(token.as_bytes()), seed).unwrap_or(0) as u64;
            hash_value = (hash_value * self.base + token_hash) % self.modulus;
        }
        hash_value
    }

    fn hash_sequence_batch(&self, token_hashes: Vec<u64>) -> u64 {
        let mut hash_value: u64 = 0;
        for th in &token_hashes {
            hash_value = (hash_value * self.base + th) % self.modulus;
        }
        hash_value
    }

    fn kgram_hashes(&self, tokens: Vec<String>, k: usize, seed: u32) -> Vec<(u64, usize)> {
        use murmur3::murmur3_32;
        use std::io::Cursor;
        if tokens.len() < k || k == 0 {
            return Vec::new();
        }
        let token_hashes: Vec<u64> = tokens
            .iter()
            .map(|t| murmur3_32(&mut Cursor::new(t.as_bytes()), seed).unwrap_or(0) as u64)
            .collect();

        let mut result = Vec::with_capacity(tokens.len() - k + 1);
        let mut hash_value: u64 = 0;
        let base_pow_k = self.base.pow(k as u32) % self.modulus;

        for i in 0..tokens.len() {
            hash_value = (hash_value * self.base + token_hashes[i]) % self.modulus;
            if i >= k {
                let old = (token_hashes[i - k] * base_pow_k) % self.modulus;
                hash_value = (hash_value + self.modulus - old) % self.modulus;
            }
            if i >= k - 1 {
                result.push((hash_value, i - k + 1));
            }
        }
        result
    }
}
