"""
PyEcharts可视化增强 - 交互式图表生成

基于pyecharts生成代码相似度热力图、关系图、直方图等。
比D3.js更易用，中文文档完善，华为生态友好。

Author: ModuleMirror
"""

from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    from pyecharts import options as opts
    from pyecharts.charts import HeatMap, Graph, Bar, Pie, Line, Grid
    from pyecharts.commons.utils import JsCode

    HAS_PYECHARTS = True
except ImportError:
    HAS_PYECHARTS = False
    opts = None
    HeatMap = Graph = Bar = Pie = Line = Grid = None

from ...utils.logger import logger


def generate_similarity_heatmap(
    modules: List[str],
    similarity_matrix: List[List[float]],
    title: str = "代码相似度热力图",
    output_path: Optional[str] = None,
) -> Optional[str]:
    if not HAS_PYECHARTS:
        logger.warning("pyecharts未安装，请运行: pip install pyecharts")
        return None

    n = len(modules)
    if n == 0 or n > 100:
        logger.warning(f"模块数{n}不适合热力图，跳过")
        return None

    data = []
    for i in range(n):
        for j in range(n):
            data.append([i, j, similarity_matrix[i][j]])

    hm = (
        HeatMap()
        .add_xaxis([m[:20] for m in modules])
        .add_yaxis(
            "相似度",
            [m[:20] for m in modules],
            data,
            label_opts=opts.LabelOpts(is_show=False),
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title),
            visualmap_opts=opts.VisualMapOpts(
                min_=0,
                max_=100,
                is_calculable=True,
                orient="horizontal",
                pos_left="center",
                pos_bottom="5%",
            ),
            xaxis_opts=opts.AxisOpts(
                type_="category",
                axislabel_opts=opts.LabelOpts(rotate=45),
            ),
            yaxis_opts=opts.AxisOpts(type_="category"),
            tooltip_opts=opts.TooltipOpts(
                formatter=JsCode(
                    "function(params){return '相似度: ' + params.value[2].toFixed(1) + '%';}"
                )
            ),
        )
    )

    if output_path:
        hm.render(output_path)
        logger.info(f"热力图已生成: {output_path}")

    return hm.render_embed() if not output_path else output_path


def generate_similarity_graph(
    nodes: List[Dict[str, Any]],
    links: List[Dict[str, Any]],
    title: str = "代码相似度关系图",
    output_path: Optional[str] = None,
) -> Optional[str]:
    if not HAS_PYECHARTS:
        logger.warning("pyecharts未安装")
        return None

    graph_nodes = []
    for node in nodes:
        graph_nodes.append(
            opts.GraphNode(
                name=node.get("name", node.get("id", "")),
                symbol_size=node.get("size", 20),
                category=node.get("category", 0),
                value=node.get("value"),
            )
        )

    graph_links = []
    for link in links:
        graph_links.append(
            opts.GraphLink(
                source=link.get("source", ""),
                target=link.get("target", ""),
                value=link.get("value", 0),
            )
        )

    categories = [
        opts.GraphCategory(name="模块"),
        opts.GraphCategory(name="高相似"),
        opts.GraphCategory(name="低相似"),
    ]

    graph = (
        Graph()
        .add(
            "",
            graph_nodes,
            graph_links,
            categories=categories,
            layout="force",
            is_roam=True,
            is_focusnode=True,
            is_draggable=True,
            repulsion=1000,
            gravity=0.1,
            edge_length=[50, 200],
            edge_symbol=["circle", "arrow"],
            edge_symbol_size=[4, 10],
            label_opts=opts.LabelOpts(is_show=True, position="right"),
            linestyle_opts=opts.LineStyleOpts(
                width=0.5,
                curve=0.3,
                opacity=0.7,
            ),
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title),
            legend_opts=opts.LegendOpts(orient="vertical", pos_left="2%", pos_top="20%"),
            tooltip_opts=opts.TooltipOpts(
                formatter=JsCode(
                    "function(params){if(params.dataType=='edge'){return '相似度: ' + params.data.value.toFixed(1) + '%';}return params.name;}"
                )
            ),
        )
    )

    if output_path:
        graph.render(output_path)
        logger.info(f"关系图已生成: {output_path}")

    return graph.render_embed() if not output_path else output_path


def generate_similarity_histogram(
    similarities: List[float],
    title: str = "相似度分布",
    bins: int = 20,
    output_path: Optional[str] = None,
) -> Optional[str]:
    if not HAS_PYECHARTS:
        logger.warning("pyecharts未安装")
        return None

    import numpy as np

    counts, edges = np.histogram(similarities, bins=bins, range=(0, 100))

    x_data = [f"{edges[i]:.0f}-{edges[i + 1]:.0f}%" for i in range(len(edges) - 1)]

    bar = (
        Bar()
        .add_xaxis(x_data)
        .add_yaxis("模块对数量", counts.tolist(), color="#5470c6")
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title),
            xaxis_opts=opts.AxisOpts(
                name="相似度区间",
                axislabel_opts=opts.LabelOpts(rotate=45),
            ),
            yaxis_opts=opts.AxisOpts(name="数量"),
            tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="shadow"),
        )
    )

    if output_path:
        bar.render(output_path)
        logger.info(f"直方图已生成: {output_path}")

    return bar.render_embed() if not output_path else output_path


def generate_similarity_pie(
    category_counts: Dict[str, int],
    title: str = "相似度分级分布",
    output_path: Optional[str] = None,
) -> Optional[str]:
    if not HAS_PYECHARTS:
        logger.warning("pyecharts未安装")
        return None

    if not category_counts:
        logger.warning("无数据，跳过饼图生成")
        return None

    data = [(k, v) for k, v in category_counts.items()]

    pie = (
        Pie()
        .add(
            "",
            data,
            radius=["30%", "70%"],
            rosetype="radius",
        )
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title),
            legend_opts=opts.LegendOpts(orient="vertical", pos_left="2%", pos_top="20%"),
            tooltip_opts=opts.TooltipOpts(trigger="item", formatter="{b}: {c} ({d}%)"),
        )
        .set_series_opts(label_opts=opts.LabelOpts(formatter="{b}: {c}"))
    )

    if output_path:
        pie.render(output_path)
        logger.info(f"饼图已生成: {output_path}")

    return pie.render_embed() if not output_path else output_path


def generate_dashboard(
    results: List[Dict[str, Any]],
    output_dir: str = "report",
) -> Dict[str, str]:
    if not HAS_PYECHARTS:
        logger.warning("pyecharts未安装，无法生成仪表盘")
        return {}

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    modules = set()
    similarities = []
    links = []
    category_counts = {"高相似(>=90%)": 0, "中相似(70-90%)": 0, "低相似(<70%)": 0}

    for r in results:
        src = r.get("source_module", r.get("source_project", ""))
        tgt = r.get("target_module", r.get("target_project", ""))
        sim = r.get("similarity", 0)

        if src:
            modules.add(src)
        if tgt:
            modules.add(tgt)

        if isinstance(sim, (int, float)):
            similarities.append(sim)
            if sim >= 90:
                category_counts["高相似(>=90%)"] += 1
            elif sim >= 70:
                category_counts["中相似(70-90%)"] += 1
            else:
                category_counts["低相似(<70%)"] += 1

            links.append({"source": src, "target": tgt, "value": sim})

    module_list = sorted(modules)
    n = len(module_list)
    idx = {m: i for i, m in enumerate(module_list)}

    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 100.0
    for r in results:
        src = r.get("source_module", r.get("source_project", ""))
        tgt = r.get("target_module", r.get("target_project", ""))
        sim = r.get("similarity", 0)
        if src in idx and tgt in idx:
            si, ti = idx[src], idx[tgt]
            matrix[si][ti] = max(matrix[si][ti], float(sim))
            matrix[ti][si] = max(matrix[ti][si], float(sim))

    output_files = {}

    if n > 0 and n <= 100:
        heatmap_path = str(output / "heatmap.html")
        generate_similarity_heatmap(module_list, matrix, output_path=heatmap_path)
        output_files["heatmap"] = heatmap_path

    if links:
        nodes = [{"name": m, "category": 0} for m in module_list]
        graph_path = str(output / "graph.html")
        generate_similarity_graph(nodes, links, output_path=graph_path)
        output_files["graph"] = graph_path

    if similarities:
        hist_path = str(output / "histogram.html")
        generate_similarity_histogram(similarities, output_path=hist_path)
        output_files["histogram"] = hist_path

        pie_path = str(output / "pie.html")
        generate_similarity_pie(category_counts, output_path=pie_path)
        output_files["pie"] = pie_path

    logger.info(f"仪表盘已生成: {len(output_files)}个文件")
    return output_files
