use pyo3::prelude::*;
use std::collections::VecDeque;

#[pyclass]
pub struct PyWinnowing {
    window_size: usize,
    kgram_size: usize,
}

#[pymethods]
impl PyWinnowing {
    #[new]
    #[pyo3(signature = (window_size=5, kgram_size=15))]
    fn new(window_size: usize, kgram_size: usize) -> Self {
        Self {
            window_size,
            kgram_size,
        }
    }

    fn winnow(&self, kgram_hashes: Vec<(u64, usize)>) -> Vec<u64> {
        let n = kgram_hashes.len();
        if n == 0 {
            return Vec::new();
        }
        if n <= self.window_size {
            return kgram_hashes.iter().map(|(h, _)| *h).collect();
        }

        let mut fingerprints: Vec<u64> = Vec::new();
        let mut deq: VecDeque<usize> = VecDeque::new();
        let mut last_selected_pos: isize = -1;

        for i in 0..n {
            while !deq.is_empty() && kgram_hashes[*deq.back().unwrap()].0 >= kgram_hashes[i].0 {
                deq.pop_back();
            }
            deq.push_back(i);

            while !deq.is_empty() && *deq.front().unwrap() + self.window_size <= i {
                deq.pop_front();
            }

            if i >= self.window_size - 1 {
                let min_idx = *deq.front().unwrap();
                if min_idx as isize != last_selected_pos {
                    fingerprints.push(kgram_hashes[min_idx].0);
                    last_selected_pos = min_idx as isize;
                }
            }
        }

        fingerprints
    }

    fn generate_fingerprints(&self, tokens: Vec<String>, seed: u32) -> Vec<u64> {
        use murmur3::murmur3_32;
        use std::io::Cursor;

        if tokens.is_empty() {
            return Vec::new();
        }

        if tokens.len() < self.kgram_size {
            let mut hash_value: u64 = 0;
            let base: u64 = 257;
            let modulus: u64 = 2_147_483_647;
            for token in &tokens {
                let th = murmur3_32(&mut Cursor::new(token.as_bytes()), seed).unwrap_or(0) as u64;
                hash_value = (hash_value * base + th) % modulus;
            }
            return vec![hash_value];
        }

        let token_hashes: Vec<u64> = tokens
            .iter()
            .map(|t| murmur3_32(&mut Cursor::new(t.as_bytes()), seed).unwrap_or(0) as u64)
            .collect();

        let base: u64 = 257;
        let modulus: u64 = 2_147_483_647;
        let base_pow_k = base.pow(self.kgram_size as u32) % modulus;

        let mut kgram_hashes: Vec<(u64, usize)> = Vec::with_capacity(tokens.len() - self.kgram_size + 1);
        let mut hash_value: u64 = 0;

        for i in 0..token_hashes.len() {
            hash_value = (hash_value * base + token_hashes[i]) % modulus;
            if i >= self.kgram_size {
                let old = (token_hashes[i - self.kgram_size] * base_pow_k) % modulus;
                hash_value = (hash_value + modulus - old) % modulus;
            }
            if i >= self.kgram_size - 1 {
                kgram_hashes.push((hash_value, i - self.kgram_size + 1));
            }
        }

        self.winnow(kgram_hashes)
    }

    fn generate_fingerprints_parallel(&self, tokens: Vec<String>, seed: u32) -> Vec<u64> {
        use murmur3::murmur3_32;
        use rayon::prelude::*;
        use std::io::Cursor;

        if tokens.is_empty() {
            return Vec::new();
        }

        let token_hashes: Vec<u64> = tokens
            .par_iter()
            .map(|t| murmur3_32(&mut Cursor::new(t.as_bytes()), seed).unwrap_or(0) as u64)
            .collect();

        if token_hashes.len() < self.kgram_size {
            let mut hash_value: u64 = 0;
            let base: u64 = 257;
            let modulus: u64 = 2_147_483_647;
            for th in &token_hashes {
                hash_value = (hash_value * base + th) % modulus;
            }
            return vec![hash_value];
        }

        let base: u64 = 257;
        let modulus: u64 = 2_147_483_647;
        let base_pow_k = base.pow(self.kgram_size as u32) % modulus;

        let mut kgram_hashes: Vec<(u64, usize)> = Vec::with_capacity(token_hashes.len() - self.kgram_size + 1);
        let mut hash_value: u64 = 0;

        for i in 0..token_hashes.len() {
            hash_value = (hash_value * base + token_hashes[i]) % modulus;
            if i >= self.kgram_size {
                let old = (token_hashes[i - self.kgram_size] * base_pow_k) % modulus;
                hash_value = (hash_value + modulus - old) % modulus;
            }
            if i >= self.kgram_size - 1 {
                kgram_hashes.push((hash_value, i - self.kgram_size + 1));
            }
        }

        self.winnow(kgram_hashes)
    }
}
