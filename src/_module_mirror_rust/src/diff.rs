use pyo3::prelude::*;
use similar::{Algorithm, TextDiff, capture_diff_slices, get_diff_ratio};

#[derive(Clone)]
#[pyclass]
pub struct PyDiffLine {
    #[pyo3(get)]
    tag: String,
    #[pyo3(get)]
    content: String,
    #[pyo3(get)]
    source_line: Option<usize>,
    #[pyo3(get)]
    target_line: Option<usize>,
}

#[pyclass]
pub struct PyDiffResult {
    #[pyo3(get)]
    lines: Vec<PyDiffLine>,
    #[pyo3(get)]
    ratio: f64,
    #[pyo3(get)]
    source_total: usize,
    #[pyo3(get)]
    target_total: usize,
    #[pyo3(get)]
    added: usize,
    #[pyo3(get)]
    removed: usize,
    #[pyo3(get)]
    unchanged: usize,
}

#[pymethods]
impl PyDiffResult {
    fn __repr__(&self) -> String {
        format!(
            "DiffResult(ratio={:.4}, +{}/-{}/={})",
            self.ratio, self.added, self.removed, self.unchanged
        )
    }
}

pub fn text_diff_impl(
    source_code: String,
    target_code: String,
    _context_lines: usize,
) -> PyDiffResult {
    let source_lines: Vec<&str> = source_code.lines().collect();
    let target_lines: Vec<&str> = target_code.lines().collect();

    let diff = TextDiff::from_lines(&source_code, &target_code);

    let ratio = diff.ratio();

    let mut lines = Vec::new();
    let mut added = 0usize;
    let mut removed = 0usize;
    let mut unchanged = 0usize;
    let mut src_idx = 0usize;
    let mut tgt_idx = 0usize;

    for change in diff.iter_all_changes() {
        let tag = match change.tag() {
            similar::ChangeTag::Delete => {
                removed += 1;
                src_idx += 1;
                "remove"
            }
            similar::ChangeTag::Insert => {
                added += 1;
                tgt_idx += 1;
                "add"
            }
            similar::ChangeTag::Equal => {
                unchanged += 1;
                let sl = src_idx + 1;
                let tl = tgt_idx + 1;
                src_idx += 1;
                tgt_idx += 1;
                lines.push(PyDiffLine {
                    tag: "equal".to_string(),
                    content: change.to_string().trim_end_matches('\n').to_string(),
                    source_line: Some(sl),
                    target_line: Some(tl),
                });
                continue;
            }
        };

        let (sl, tl) = if tag == "remove" {
            (Some(src_idx), None)
        } else {
            (None, Some(tgt_idx))
        };

        lines.push(PyDiffLine {
            tag: tag.to_string(),
            content: change.to_string().trim_end_matches('\n').to_string(),
            source_line: sl,
            target_line: tl,
        });
    }

    PyDiffResult {
        lines,
        ratio: ratio as f64,
        source_total: source_lines.len(),
        target_total: target_lines.len(),
        added,
        removed,
        unchanged,
    }
}

pub fn unified_diff_impl(
    source_code: String,
    target_code: String,
    source_name: String,
    target_name: String,
    _context_lines: usize,
) -> String {
    let diff = TextDiff::from_lines(&source_code, &target_code);

    let mut output = String::new();

    for hunk in diff.unified_diff().header(&source_name, &target_name).iter_hunks() {
        output.push_str(&hunk.to_string());
    }

    output
}

pub fn sequence_ratio_impl(source: Vec<String>, target: Vec<String>) -> f64 {
    if source.is_empty() && target.is_empty() {
        return 1.0;
    }
    if source.is_empty() || target.is_empty() {
        return 0.0;
    }

    let source_refs: Vec<&str> = source.iter().map(|s| s.as_str()).collect();
    let target_refs: Vec<&str> = target.iter().map(|s| s.as_str()).collect();

    let ops = capture_diff_slices(Algorithm::Patience, &source_refs, &target_refs);
    get_diff_ratio(&ops, source_refs.len(), target_refs.len()) as f64
}
