use pyo3::prelude::*;
use rayon::prelude::*;
use simsimd::SpatialSimilarity;

pub fn cosine_similarity_impl(a: Vec<f64>, b: Vec<f64>) -> PyResult<f64> {
    if a.len() != b.len() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Vectors must have the same length",
        ));
    }
    if a.is_empty() {
        return Ok(0.0);
    }
    let cos_result = <f64 as SpatialSimilarity>::cos(&a, &b);
    match cos_result {
        Some(distance) => {
            let sim = 1.0 - distance;
            Ok(if sim > 1.0 { 1.0 } else if sim < -1.0 { -1.0 } else { sim })
        }
        None => {
            let dot: f64 = a.iter().zip(&b).map(|(x, y)| x * y).sum();
            let na: f64 = a.iter().map(|x| x * x).sum::<f64>().sqrt();
            let nb: f64 = b.iter().map(|x| x * x).sum::<f64>().sqrt();
            if na == 0.0 || nb == 0.0 {
                Ok(0.0)
            } else {
                Ok(dot / (na * nb))
            }
        }
    }
}

pub fn euclidean_distance_impl(a: Vec<f64>, b: Vec<f64>) -> PyResult<f64> {
    if a.len() != b.len() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Vectors must have the same length",
        ));
    }
    if a.is_empty() {
        return Ok(0.0);
    }
    let sq_result = <f64 as SpatialSimilarity>::sqeuclidean(&a, &b);
    match sq_result {
        Some(sq_dist) => Ok(sq_dist.sqrt()),
        None => Ok(a
            .iter()
            .zip(&b)
            .map(|(x, y)| (x - y) * (x - y))
            .sum::<f64>()
            .sqrt()),
    }
}

pub fn l2_normalize_impl(v: Vec<f64>) -> Vec<f64> {
    let norm: f64 = v.iter().map(|x| x * x).sum::<f64>().sqrt();
    if norm == 0.0 {
        return v;
    }
    v.iter().map(|x| x / norm).collect()
}

pub fn batch_cosine_similarity_impl(
    query: Vec<f64>,
    candidates: Vec<Vec<f64>>,
) -> PyResult<Vec<f64>> {
    let results: PyResult<Vec<f64>> = candidates
        .iter()
        .map(|c| cosine_similarity_impl(query.clone(), c.clone()))
        .collect();
    results
}

pub fn batch_cosine_similarity_parallel_impl(
    query: Vec<f64>,
    candidates: Vec<Vec<f64>>,
) -> PyResult<Vec<f64>> {
    let results: Vec<PyResult<f64>> = candidates
        .par_iter()
        .map(|c| cosine_similarity_impl(query.clone(), c.clone()))
        .collect();
    results.into_iter().collect()
}

struct PathExtractor;

impl PathExtractor {
    fn extract_ast_paths(
        code: &str,
        max_paths: usize,
        path_length: usize,
    ) -> Vec<(String, String, String)> {
        let mut paths = Vec::new();
        let mut tokens: Vec<(String, usize)> = Vec::new();

        for (i, line) in code.split('\n').enumerate() {
            for tok in line.trim().split_whitespace() {
                if !tok.is_empty() && !tok.starts_with('#') {
                    tokens.push((tok.to_string(), i));
                }
            }
        }

        for i in 0..tokens.len() {
            for j in (i + 1)..tokens.len() {
                if tokens[j].1 - tokens[i].1 > path_length {
                    continue;
                }
                let mid_idx = (i + j) / 2;
                let mid = if mid_idx < tokens.len() {
                    tokens[mid_idx].0.as_str()
                } else {
                    ""
                };
                paths.push((tokens[i].0.clone(), mid.to_string(), tokens[j].0.clone()));
                if paths.len() >= max_paths {
                    return paths;
                }
            }
        }
        paths
    }

    fn path_to_hash(path: &(String, String, String)) -> u64 {
        use std::hash::{Hash, Hasher};
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        path.0.hash(&mut hasher);
        "|".hash(&mut hasher);
        path.1.hash(&mut hasher);
        "|".hash(&mut hasher);
        path.2.hash(&mut hasher);
        hasher.finish()
    }

    fn initialize_weights(dimension: usize) -> Vec<f64> {
        let mut seed = 42u64;
        let mut weights = Vec::with_capacity(dimension);
        for _ in 0..dimension {
            seed = (seed.wrapping_mul(1103515245).wrapping_add(12345)) & 0x7FFFFFFF;
            weights.push((seed as f64 / 0x7FFFFFFF as f64) - 0.5);
        }
        weights
    }
}

pub fn code2vec_embed_impl(
    code: String,
    dimension: usize,
    max_paths: usize,
    path_length: usize,
) -> (Vec<f64>, usize) {
    let weights = PathExtractor::initialize_weights(dimension);
    let paths = PathExtractor::extract_ast_paths(&code, max_paths, path_length);
    let num_paths = paths.len();
    let mut vector = vec![0.0f64; dimension];

    if paths.is_empty() {
        for i in 0..dimension {
            vector[i] = weights[i] * 0.01;
        }
        return (vector, num_paths);
    } else {
        for path in &paths {
            let h = PathExtractor::path_to_hash(path);
            for i in 0..dimension {
                let angle = (h as f64 + i as f64) * 0.618033988749895;
                vector[i] += angle.sin() * weights[i % weights.len()];
            }
        }
        (l2_normalize_impl(vector), num_paths)
    }
}

pub fn vectors_to_lsh_hash_impl(
    vector: Vec<f64>,
    num_bands: usize,
    band_width: usize,
) -> Vec<String> {
    use std::hash::{Hash, Hasher};
    let mut hashes = Vec::with_capacity(num_bands);
    for band_idx in 0..num_bands {
        let start = band_idx * band_width;
        let end = start + band_width;
        let band_str: String = vector[start..end.min(vector.len())]
            .iter()
            .map(|v| format!("{v:.4}"))
            .collect::<Vec<_>>()
            .join(",");
        let mut hasher = std::collections::hash_map::DefaultHasher::new();
        band_str.hash(&mut hasher);
        let h = format!("{:08x}", hasher.finish());
        hashes.push(format!("b{band_idx}:{h}"));
    }
    hashes
}
