"""
多代码视图融合测试 - AST + DFG + CFG 三视图

Author: ModuleMirror
"""

from gh_similarity_detector.core.similarity.multiview_fusion import (
    ViewType,
    ViewFeature,
    MultiViewFeature,
    ASTViewExtractor,
    DFGViewExtractor,
    CFGViewExtractor,
    MultiViewFusion,
)


class TestViewFeature:
    def test_default_values(self):
        vf = ViewFeature(view_type=ViewType.AST)
        assert vf.node_types == []
        assert vf.edge_types == []
        assert vf.depth == 0
        assert vf.node_count == 0
        assert vf.edge_count == 0

    def test_to_dict(self):
        vf = ViewFeature(
            view_type=ViewType.AST,
            node_types=["function_def", "call"],
            edge_types=["call_edge"],
            depth=2,
            node_count=3,
            edge_count=1,
        )
        d = vf.to_dict()
        assert d["view_type"] == "ast"
        assert d["node_types"] == ["function_def", "call"]
        assert d["depth"] == 2
        assert "structural_hash" not in d


class TestMultiViewFeature:
    def test_fused_hash_deterministic(self):
        mf = MultiViewFeature(
            code_id="test",
            ast_feature=ViewFeature(view_type=ViewType.AST, structural_hash="aaa"),
            dfg_feature=ViewFeature(view_type=ViewType.DFG, structural_hash="bbb"),
            cfg_feature=ViewFeature(view_type=ViewType.CFG, structural_hash="ccc"),
        )
        h1 = mf.fused_hash()
        h2 = mf.fused_hash()
        assert h1 == h2
        assert len(h1) == 16

    def test_fused_hash_different_inputs(self):
        mf1 = MultiViewFeature(
            code_id="a",
            ast_feature=ViewFeature(view_type=ViewType.AST, structural_hash="x"),
            dfg_feature=ViewFeature(view_type=ViewType.DFG, structural_hash="y"),
            cfg_feature=ViewFeature(view_type=ViewType.CFG, structural_hash="z"),
        )
        mf2 = MultiViewFeature(
            code_id="b",
            ast_feature=ViewFeature(view_type=ViewType.AST, structural_hash="p"),
            dfg_feature=ViewFeature(view_type=ViewType.DFG, structural_hash="q"),
            cfg_feature=ViewFeature(view_type=ViewType.CFG, structural_hash="r"),
        )
        assert mf1.fused_hash() != mf2.fused_hash()

    def test_fused_similarity_identical(self):
        vf_ast = ViewFeature(
            view_type=ViewType.AST,
            node_types=["function_def", "call"],
            depth=2,
            node_count=5,
        )
        mf1 = MultiViewFeature(code_id="a", ast_feature=vf_ast)
        mf2 = MultiViewFeature(code_id="b", ast_feature=vf_ast)
        sim = mf1.fused_similarity(mf2)
        assert sim > 0.8

    def test_fused_similarity_empty(self):
        mf1 = MultiViewFeature(code_id="a")
        mf2 = MultiViewFeature(code_id="b")
        sim = mf1.fused_similarity(mf2)
        assert sim == 1.0

    def test_fused_similarity_custom_weights(self):
        mf1 = MultiViewFeature(code_id="a")
        mf2 = MultiViewFeature(code_id="b")
        sim = mf1.fused_similarity(mf2, weights={"ast": 1.0, "dfg": 0.0, "cfg": 0.0})
        assert sim == 1.0

    def test_to_dict(self):
        mf = MultiViewFeature(code_id="test")
        d = mf.to_dict()
        assert d["code_id"] == "test"
        assert "fused_hash" in d
        assert "ast" in d
        assert "dfg" in d
        assert "cfg" in d


class TestASTViewExtractor:
    def test_extract_simple_function(self):
        code = "def foo():\n    return 1"
        vf = ASTViewExtractor().extract(code)
        assert vf.view_type == ViewType.AST
        assert "function_def" in vf.node_types
        assert "return" in vf.node_types
        assert vf.depth >= 1

    def test_extract_class_with_methods(self):
        code = "class Foo:\n    def bar(self):\n        pass"
        vf = ASTViewExtractor().extract(code)
        assert "class_def" in vf.node_types
        assert "function_def" in vf.node_types

    def test_extract_conditional(self):
        code = "if x:\n    pass\nelif y:\n    pass"
        vf = ASTViewExtractor().extract(code)
        assert "conditional" in vf.node_types
        assert "branch" in vf.edge_types

    def test_extract_loop(self):
        code = "for i in range(10):\n    print(i)"
        vf = ASTViewExtractor().extract(code)
        assert "loop" in vf.node_types
        assert "loop_edge" in vf.edge_types

    def test_extract_imports(self):
        code = "import os\nfrom sys import path"
        vf = ASTViewExtractor().extract(code)
        assert "import" in vf.node_types
        assert "dep" in vf.edge_types

    def test_extract_empty(self):
        vf = ASTViewExtractor().extract("")
        assert vf.node_count == 0

    def test_structural_hash_consistent(self):
        code = "def foo():\n    return 1"
        h1 = ASTViewExtractor().extract(code).structural_hash
        h2 = ASTViewExtractor().extract(code).structural_hash
        assert h1 == h2


class TestDFGViewExtractor:
    def test_extract_assignment_and_use(self):
        code = "x = 1\ny = x + 2"
        vf = DFGViewExtractor().extract(code)
        assert vf.view_type == ViewType.DFG
        assert vf.node_count > 0

    def test_extract_def_use_edges(self):
        code = "a = 1\nb = a"
        vf = DFGViewExtractor().extract(code)
        assert "def" in vf.edge_types
        assert "use" in vf.edge_types

    def test_extract_no_definitions(self):
        code = "print(1)"
        vf = DFGViewExtractor().extract(code)
        assert vf.view_type == ViewType.DFG

    def test_extract_empty(self):
        vf = DFGViewExtractor().extract("")
        assert vf.node_count == 0


class TestCFGViewExtractor:
    def test_extract_branch(self):
        code = "if x:\n    pass"
        vf = CFGViewExtractor().extract(code)
        assert vf.view_type == ViewType.CFG
        assert "branch_block" in vf.node_types
        assert "branch" in vf.edge_types

    def test_extract_loop(self):
        code = "while True:\n    break"
        vf = CFGViewExtractor().extract(code)
        assert "loop_block" in vf.node_types
        assert "loop_back" in vf.edge_types
        assert vf.depth == 2

    def test_extract_try_except(self):
        code = "try:\n    pass\nexcept:\n    pass"
        vf = CFGViewExtractor().extract(code)
        assert "exception_block" in vf.node_types
        assert "exception" in vf.edge_types

    def test_extract_entry_exit(self):
        code = "x = 1"
        vf = CFGViewExtractor().extract(code)
        assert "entry" in vf.node_types
        assert "exit" in vf.node_types

    def test_extract_return(self):
        code = "def foo():\n    return 1"
        vf = CFGViewExtractor().extract(code)
        assert "exit" in vf.node_types

    def test_extract_continue(self):
        code = "while True:\n    continue"
        vf = CFGViewExtractor().extract(code)
        assert "loop_entry" in vf.node_types
        assert "continue" in vf.edge_types


class TestMultiViewFusion:
    SIMPLE_CODE = "def foo(x):\n    if x > 0:\n        return x\n    return 0"

    def test_extract(self):
        fusion = MultiViewFusion()
        mf = fusion.extract(self.SIMPLE_CODE, code_id="test1")
        assert mf.code_id == "test1"
        assert mf.ast_feature.view_type == ViewType.AST
        assert mf.dfg_feature.view_type == ViewType.DFG
        assert mf.cfg_feature.view_type == ViewType.CFG

    def test_extract_auto_code_id(self):
        fusion = MultiViewFusion()
        mf = fusion.extract(self.SIMPLE_CODE)
        assert len(mf.code_id) == 8

    def test_compute_similarity_same_code(self):
        fusion = MultiViewFusion()
        mf1 = fusion.extract(self.SIMPLE_CODE, "a")
        mf2 = fusion.extract(self.SIMPLE_CODE, "b")
        sim = fusion.compute_similarity(mf1, mf2)
        assert sim > 0.9

    def test_compute_similarity_different_code(self):
        fusion = MultiViewFusion()
        code1 = "def foo(x):\n    return x"
        code2 = "class Bar:\n    def baz(self):\n        pass"
        mf1 = fusion.extract(code1, "a")
        mf2 = fusion.extract(code2, "b")
        sim = fusion.compute_similarity(mf1, mf2)
        assert 0.0 <= sim <= 1.0

    def test_compute_similarity_custom_weights(self):
        fusion = MultiViewFusion()
        mf1 = fusion.extract(self.SIMPLE_CODE, "a")
        mf2 = fusion.extract(self.SIMPLE_CODE, "b")
        sim = fusion.compute_similarity(mf1, mf2, weights={"ast": 0.5, "dfg": 0.3, "cfg": 0.2})
        assert 0.0 <= sim <= 1.0

    def test_round_trip_to_dict(self):
        fusion = MultiViewFusion()
        mf = fusion.extract(self.SIMPLE_CODE, "test")
        d = mf.to_dict()
        assert d["code_id"] == "test"
        assert "ast" in d
        assert "dfg" in d
        assert "cfg" in d
