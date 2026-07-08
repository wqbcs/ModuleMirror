"""算法插件系统测试 (L3 可扩展 + SimHash 算法实现)"""

from __future__ import annotations

from fastapi.testclient import TestClient

from gh_similarity_detector.api.app import app
from gh_similarity_detector.infrastructure.plugins.builtin import (
    SimHashAlgorithm,
    _jaccard,
    _simhash_similarity,
)
from gh_similarity_detector.infrastructure.plugins.manager import (
    get_algorithm_plugin_manager,
)

client = TestClient(app)


def test_builtin_algorithms_registered() -> None:
    mgr = get_algorithm_plugin_manager()
    names = set(mgr.names())
    assert {"winnowing", "containment", "simhash"} <= names


def test_jaccard_basic() -> None:
    assert _jaccard({1, 2, 3}, {2, 3, 4}) == 2 / 4
    assert _jaccard(set(), set()) == 0.0


def test_simhash_identical_is_one() -> None:
    s = {10, 20, 30, 40}
    assert _simhash_similarity(s, s) == 1.0


def test_simhash_range() -> None:
    a = {1, 2, 3, 4, 5}
    b = {100, 200, 300, 400, 500}
    score = _simhash_similarity(a, b)
    assert 0.0 <= score <= 1.0


def test_algorithm_plugin_similarity_in_range() -> None:
    algo = SimHashAlgorithm()
    score = algo.similarity({1, 2, 3}, {1, 2, 9})
    assert 0.0 <= score <= 1.0


def test_api_list_algorithms() -> None:
    r = client.get("/v1/algorithms")
    assert r.status_code == 200
    names = {a["name"] for a in r.json()["algorithms"]}
    assert {"winnowing", "containment", "simhash"} <= names


def test_api_get_algorithm_detail() -> None:
    r = client.get("/v1/algorithms/simhash")
    assert r.status_code == 200
    assert r.json()["name"] == "simhash"


def test_api_algorithm_not_found() -> None:
    assert client.get("/v1/algorithms/nope").status_code == 404


def test_api_compute_similarity() -> None:
    r = client.post(
        "/v1/algorithms/simhash/similarity",
        json={"a": [1, 2, 3, 4], "b": [1, 2, 3, 4]},
    )
    assert r.status_code == 200
    assert r.json()["similarity"] == 1.0
