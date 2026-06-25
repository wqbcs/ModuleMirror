mod diff;
mod embedding;
mod lsh;
mod minhash;
mod rolling_hash;
mod simd_batch;
mod tokenizer;
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

#[pyfunction]
fn jaccard_sorted(set1: Vec<i64>, set2: Vec<i64>) -> f64 {
    simd_batch::jaccard_sorted_impl(set1, set2)
}

#[pyfunction]
fn jaccard_sorted_many(query: Vec<i64>, candidates: Vec<Vec<i64>>) -> Vec<f64> {
    simd_batch::jaccard_sorted_many_impl(query, candidates)
}

#[pyfunction]
fn jaccard_sorted_many_parallel(query: Vec<i64>, candidates: Vec<Vec<i64>>) -> Vec<f64> {
    simd_batch::jaccard_sorted_many_parallel_impl(query, candidates)
}

#[pyfunction]
fn intersection_sorted(set1: Vec<i64>, set2: Vec<i64>) -> Vec<i64> {
    simd_batch::intersection_sorted_impl(set1, set2)
}

#[pyfunction]
fn find_duplicates(hash_array: Vec<i64>, module_ids: Vec<i32>) -> HashMap<i32, Vec<i32>> {
    simd_batch::find_duplicates_impl(hash_array, module_ids)
}

#[pyfunction]
fn cosine_similarity(a: Vec<f64>, b: Vec<f64>) -> PyResult<f64> {
    embedding::cosine_similarity_impl(a, b)
}

#[pyfunction]
fn euclidean_distance(a: Vec<f64>, b: Vec<f64>) -> PyResult<f64> {
    embedding::euclidean_distance_impl(a, b)
}

#[pyfunction]
fn l2_normalize(v: Vec<f64>) -> Vec<f64> {
    embedding::l2_normalize_impl(v)
}

#[pyfunction]
fn batch_cosine_similarity(query: Vec<f64>, candidates: Vec<Vec<f64>>) -> PyResult<Vec<f64>> {
    embedding::batch_cosine_similarity_impl(query, candidates)
}

#[pyfunction]
fn batch_cosine_similarity_parallel(
    query: Vec<f64>,
    candidates: Vec<Vec<f64>>,
) -> PyResult<Vec<f64>> {
    embedding::batch_cosine_similarity_parallel_impl(query, candidates)
}

#[pyfunction]
fn code2vec_embed(code: String, dimension: usize, max_paths: usize, path_length: usize) -> (Vec<f64>, usize) {
    embedding::code2vec_embed_impl(code, dimension, max_paths, path_length)
}

#[pyfunction]
fn vectors_to_lsh_hash(vector: Vec<f64>, num_bands: usize, band_width: usize) -> Vec<String> {
    embedding::vectors_to_lsh_hash_impl(vector, num_bands, band_width)
}

#[pyfunction]
fn text_diff(source_code: String, target_code: String, context_lines: usize) -> diff::PyDiffResult {
    diff::text_diff_impl(source_code, target_code, context_lines)
}

#[pyfunction]
fn unified_diff(
    source_code: String,
    target_code: String,
    source_name: String,
    target_name: String,
    context_lines: usize,
) -> String {
    diff::unified_diff_impl(source_code, target_code, source_name, target_name, context_lines)
}

#[pyfunction]
fn sequence_ratio(source: Vec<String>, target: Vec<String>) -> f64 {
    diff::sequence_ratio_impl(source, target)
}

#[pyfunction]
fn tokenize(code: String, language: String) -> Vec<String> {
    tokenizer::tokenize_impl(code, language)
}

use std::collections::HashMap;

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
    m.add_function(wrap_pyfunction!(jaccard_sorted, m)?)?;
    m.add_function(wrap_pyfunction!(jaccard_sorted_many, m)?)?;
    m.add_function(wrap_pyfunction!(jaccard_sorted_many_parallel, m)?)?;
    m.add_function(wrap_pyfunction!(intersection_sorted, m)?)?;
    m.add_function(wrap_pyfunction!(find_duplicates, m)?)?;
    m.add_class::<simd_batch::PyInvertedIndex>()?;
    m.add_function(wrap_pyfunction!(cosine_similarity, m)?)?;
    m.add_function(wrap_pyfunction!(euclidean_distance, m)?)?;
    m.add_function(wrap_pyfunction!(l2_normalize, m)?)?;
    m.add_function(wrap_pyfunction!(batch_cosine_similarity, m)?)?;
    m.add_function(wrap_pyfunction!(batch_cosine_similarity_parallel, m)?)?;
    m.add_function(wrap_pyfunction!(code2vec_embed, m)?)?;
    m.add_function(wrap_pyfunction!(vectors_to_lsh_hash, m)?)?;
    m.add_function(wrap_pyfunction!(text_diff, m)?)?;
    m.add_function(wrap_pyfunction!(unified_diff, m)?)?;
    m.add_function(wrap_pyfunction!(sequence_ratio, m)?)?;
    m.add_class::<diff::PyDiffLine>()?;
    m.add_class::<diff::PyDiffResult>()?;
    m.add_function(wrap_pyfunction!(tokenize, m)?)?;
    Ok(())
}
