"""
交互式网络图可视化 - 基于pyvis

生成代码相似度交互式网络图，支持拖拽/缩放/高亮。
可独立查看或嵌入到可视化报告中。

Author: ModuleMirror
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from pyvis.network import Network

    HAS_PYVIS = True
except ImportError:
    HAS_PYVIS = False

from ...utils.logger import logger


def generate_network_graph(
    results: List[Dict[str, Any]],
    output_path: str = "report/similarity_network.html",
    project_names: Optional[List[str]] = None,
    height: str = "800px",
    min_similarity: float = 0.0,
) -> Optional[str]:
    if not HAS_PYVIS:
        logger.warning("pyvis未安装，无法生成交互式网络图。请运行: pip install pyvis")
        return None

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    nodes, edges = _extract_graph_data(results, project_names, min_similarity)

    if not nodes:
        logger.info("无足够数据生成网络图")
        return None

    net = Network(
        height=height,
        width="100%",
        directed=False,
        notebook=False,
        heading="ModuleMirror - 代码相似度网络图",
    )

    net.barnes_hut(
        gravity=-8000,
        central_gravity=0.3,
        spring_length=150,
        spring_strength=0.001,
        damping=0.09,
    )

    for node_id, label, group in nodes:
        net.add_node(
            node_id,
            label=label,
            group=group,
            title=label,
            size=20,
        )

    for src, tgt, value, title in edges:
        color = _similarity_to_color(value)
        width = _similarity_to_width(value)
        net.add_edge(
            src,
            tgt,
            value=value,
            title=title,
            color=color,
            width=width,
        )

    net.set_options("""
    {
        "physics": {
            "barnesHut": {
                "gravitationalConstant": -8000,
                "centralGravity": 0.3,
                "springLength": 150,
                "springConstant": 0.001
            }
        },
        "interaction": {
            "hover": true,
            "tooltipDelay": 200,
            "navigationButtons": true,
            "keyboard": true
        },
        "nodes": {
            "font": {"size": 12, "face": "sans-serif"},
            "shape": "dot",
            "borderWidth": 2
        },
        "edges": {
            "smooth": {"type": "continuous"},
            "arrows": {"to": {"enabled": false}}
        }
    }
    """)

    net.save_graph(str(output))

    _inject_metadata(output, len(nodes), len(edges), min_similarity)

    logger.info(f"交互式网络图已生成: {output} ({len(nodes)}节点, {len(edges)}边)")
    return str(output)


def _extract_graph_data(
    results: List[Dict[str, Any]],
    project_names: Optional[List[str]],
    min_similarity: float,
) -> tuple[list[tuple[str, str, int]], list[tuple[str, str, float, str]]]:
    node_set = set()
    nodes = []
    edges = []
    project_idx = {}
    idx = 0

    if project_names:
        for name in project_names:
            project_idx[name] = idx
            idx += 1

    for r in results:
        src = r.get("source_project") or r.get("source_module", "")
        tgt = r.get("target_project") or r.get("target_module", "")

        if not src or not tgt:
            continue

        for m in r.get("matches", []):
            s_mod = m.get("source_module", src)
            t_mod = m.get("target_module", tgt)
            sim = m.get("similarity", 0)

            if isinstance(sim, (int, float)) and sim >= min_similarity:
                s_group = _get_project_group(s_mod, project_idx)
                t_group = _get_project_group(t_mod, project_idx)

                if s_mod not in node_set:
                    node_set.add(s_mod)
                    nodes.append((s_mod, _truncate_label(s_mod), s_group))
                if t_mod not in node_set:
                    node_set.add(t_mod)
                    nodes.append((t_mod, _truncate_label(t_mod), t_group))

                edges.append((s_mod, t_mod, sim, f"相似度: {sim:.1f}%"))

        src_sim = r.get("statistics", {}).get("avg_similarity", 0)
        if isinstance(src_sim, (int, float)) and src_sim >= min_similarity and src and tgt:
            s_group = _get_project_group(src, project_idx)
            t_group = _get_project_group(tgt, project_idx)
            if src not in node_set:
                node_set.add(src)
                nodes.append((src, _truncate_label(src), s_group))
            if tgt not in node_set:
                node_set.add(tgt)
                nodes.append((tgt, _truncate_label(tgt), t_group))
            edges.append((src, tgt, src_sim, f"平均相似度: {src_sim:.1f}%"))

    return nodes, edges


def _get_project_group(name: str, project_idx: Dict[str, int]) -> int:
    for proj_name, group in project_idx.items():
        if name.startswith(proj_name):
            return group
    return 0


def _truncate_label(label: str, max_len: int = 30) -> str:
    if len(label) <= max_len:
        return label
    return label[: max_len - 3] + "..."


def _similarity_to_color(similarity: float) -> str:
    if similarity >= 90:
        return "#dc2626"
    if similarity >= 80:
        return "#f97316"
    if similarity >= 70:
        return "#eab308"
    if similarity >= 50:
        return "#22c55e"
    return "#3b82f6"


def _similarity_to_width(similarity: float) -> float:
    return max(1.0, similarity / 20.0)


def _inject_metadata(
    output_path: Path,
    node_count: int,
    edge_count: int,
    min_similarity: float,
) -> None:
    try:
        content = output_path.read_text(encoding="utf-8")
        meta = (
            f"<!-- ModuleMirror Network Graph | "
            f"Nodes: {node_count} | Edges: {edge_count} | "
            f"Min Similarity: {min_similarity} | "
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')} -->"
        )
        content = meta + "\n" + content
        output_path.write_text(content, encoding="utf-8")
    except (OSError, UnicodeEncodeError, UnicodeDecodeError):
        logger.debug(f"DOT 文件写入失败: {output_path}")
