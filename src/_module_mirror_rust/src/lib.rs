mod lsh;
mod minhash;
mod rolling_hash;
mod winnowing;

use pyo3::prelude::*;

#[pyfunction]
fn stable_hash_rust(data: &str, seed: u32) -> u32 {
    use murmur3::murmur3_32;
    use std::io::Cursor;
    murmur3_32(&mut Cursor::new(data.as_bytes()), seed).unwrap_or(0)
}

#[pyfunction]
fn stable_hash64_rust(data: &str, seed: u32) -> u64 {
    use murmur3::murmur3_x64_128;
    use std::io::Cursor;
    let hash = murmur3_x64_128(&mut Cursor::new(data.as_bytes()), seed);
    hash.unwrap_or(0) as u64
}

#[pyfunction]
fn batch_stable_hash(tokens: Vec<String>, seed: u32) -> Vec<u32> {
    use murmur3::murmur3_32;
    use std::io::Cursor;
    tokens
        .iter()
        .map(|t| murmur3_32(&mut Cursor::new(t.as_bytes()), seed).unwrap_or(0))
        .collect()
}

#[pyfunction]
fn batch_stable_hash_parallel(tokens: Vec<String>, seed: u32) -> Vec<u32> {
    use murmur3::murmur3_32;
    use rayon::prelude::*;
    use std::io::Cursor;
    tokens
        .par_iter()
        .map(|t| murmur3_32(&mut Cursor::new(t.as_bytes()), seed).unwrap_or(0))
        .collect()
}

#[pyfunction]
fn create_minhash_signature(tokens: Vec<String>, num_perm: usize) -> Vec<u32> {
    minhash::create_minhash_signature(tokens, num_perm)
}

#[pyfunction]
fn create_minhash_signatures_batch(items: Vec<Vec<String>>, num_perm: usize) -> Vec<Vec<u32>> {
    minhash::create_minhash_signatures_batch(items, num_perm)
}

#[pyfunction]
fn create_minhash_signatures_parallel(items: Vec<Vec<String>>, num_perm: usize) -> Vec<Vec<u32>> {
    minhash::create_minhash_signatures_parallel(items, num_perm)
}

#[pyfunction]
fn estimate_jaccard(sig1: Vec<u32>, sig2: Vec<u32>) -> PyResult<f64> {
    if sig1.len() != sig2.len() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Signatures must have the same length",
        ));
    }
    Ok(minhash::estimate_jaccard_impl(&sig1, &sig2))
}

#[pymodule]
fn _module_mirror_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(stable_hash_rust, m)?)?;
    m.add_function(wrap_pyfunction!(stable_hash64_rust, m)?)?;
    m.add_function(wrap_pyfunction!(batch_stable_hash, m)?)?;
    m.add_function(wrap_pyfunction!(batch_stable_hash_parallel, m)?)?;
    m.add_class::<rolling_hash::PyRollingHash>()?;
    m.add_class::<winnowing::PyWinnowing>()?;
    m.add_class::<minhash::PyMinHash>()?;
    m.add_function(wrap_pyfunction!(create_minhash_signature, m)?)?;
    m.add_function(wrap_pyfunction!(create_minhash_signatures_batch, m)?)?;
    m.add_function(wrap_pyfunction!(create_minhash_signatures_parallel, m)?)?;
    m.add_function(wrap_pyfunction!(estimate_jaccard, m)?)?;
    m.add_class::<lsh::PyMinHashLSH>()?;
    Ok(())
}
