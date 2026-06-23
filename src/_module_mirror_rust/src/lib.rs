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

#[pymodule]
fn _module_mirror_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(stable_hash_rust, m)?)?;
    m.add_function(wrap_pyfunction!(stable_hash64_rust, m)?)?;
    m.add_function(wrap_pyfunction!(batch_stable_hash, m)?)?;
    m.add_function(wrap_pyfunction!(batch_stable_hash_parallel, m)?)?;
    m.add_class::<rolling_hash::PyRollingHash>()?;
    m.add_class::<winnowing::PyWinnowing>()?;
    Ok(())
}
