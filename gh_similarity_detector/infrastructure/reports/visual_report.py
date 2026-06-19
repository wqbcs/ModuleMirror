"""
可视化报告生成器

生成 D3.js 热力图 + 依赖图的交互式 HTML 报告。

Author: ModuleMirror
"""

import time
from pathlib import Path
from typing import Dict, List, Any, Optional

from ...utils.json_utils import dumps as json_dumps


def generate_visual_report(
    results: List[Dict[str, Any]],
    output_path: str = "report/visual_report.html",
    project_names: Optional[List[str]] = None,
) -> str:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    modules = _extract_modules(results, project_names)
    similarity_matrix = _build_matrix(results, modules)
    dependency_graph = _build_dependency_graph(results, modules)

    data = {
        "modules": modules,
        "similarity_matrix": similarity_matrix,
        "dependency_graph": dependency_graph,
        "metadata": {
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_modules": len(modules),
            "total_results": len(results),
        },
    }

    html = _render_html(data)
    output.write_text(html, encoding="utf-8")
    return str(output)


def _extract_modules(results: List[Dict], project_names: Optional[List[str]]) -> List[str]:
    modules = set()
    for r in results:
        src = r.get("source_project") or r.get("source_module", "")
        tgt = r.get("target_project") or r.get("target_module", "")
        if src:
            modules.add(src)
        if tgt:
            modules.add(tgt)
        for m in r.get("matches", []):
            for key in ("source_module", "target_module"):
                name = m.get(key, "")
                if name:
                    modules.add(name)
    return sorted(modules)


def _build_matrix(results: List[Dict], modules: List[str]) -> List[List[float]]:
    n = len(modules)
    matrix = [[0.0] * n for _ in range(n)]
    idx = {m: i for i, m in enumerate(modules)}

    for i in range(n):
        matrix[i][i] = 100.0

    for r in results:
        src = r.get("source_project") or r.get("source_module", "")
        tgt = r.get("target_project") or r.get("target_module", "")
        sim = r.get("statistics", {}).get("avg_similarity", 0)
        if isinstance(sim, (int, float)) and src in idx and tgt in idx:
            si, ti = idx[src], idx[tgt]
            matrix[si][ti] = max(matrix[si][ti], float(sim))
            matrix[ti][si] = max(matrix[ti][si], float(sim))

    return matrix


def _build_dependency_graph(results: List[Dict], modules: List[str]) -> Dict[str, Any]:
    idx = {m: i for i, m in enumerate(modules)}
    nodes = [{"id": i, "name": m, "group": 1} for i, m in enumerate(modules)]
    links = []
    link_set = set()

    for r in results:
        src = r.get("source_project") or r.get("source_module", "")
        tgt = r.get("target_project") or r.get("target_module", "")
        sim = r.get("statistics", {}).get("avg_similarity", 0)
        if isinstance(sim, (int, float)) and src in idx and tgt in idx:
            si, ti = idx[src], idx[tgt]
            key = (min(si, ti), max(si, ti))
            if key not in link_set:
                link_set.add(key)
                links.append(
                    {
                        "source": si,
                        "target": ti,
                        "value": float(sim),
                    }
                )

    return {"nodes": nodes, "links": links}


def _render_html(data: Dict[str, Any]) -> str:
    data_json = json_dumps(data, ensure_ascii=False, indent=True)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ModuleMirror - 可视化报告</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
  .heatmap-cell {{ cursor: pointer; }}
  .heatmap-cell:hover {{ stroke: #333; stroke-width: 2; }}
  .tooltip {{ position: absolute; padding: 8px 12px; background: rgba(0,0,0,0.85); color: #fff; border-radius: 6px; font-size: 12px; pointer-events: none; z-index: 100; }}
  #force-graph {{ border: 1px solid #e5e7eb; border-radius: 8px; }}
</style>
</head>
<body class="min-h-screen bg-gray-50">
<nav class="bg-white shadow-sm border-b">
  <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
    <div class="flex items-center gap-2">
      <span class="text-lg font-semibold">ModuleMirror</span>
      <span class="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">可视化报告</span>
    </div>
    <span class="text-xs text-gray-400">生成于 {data["metadata"]["generated_at"]}</span>
  </div>
</nav>

<main class="max-w-7xl mx-auto px-4 py-6 space-y-6">
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <div class="bg-white rounded-xl shadow-sm border p-6">
      <h2 class="text-lg font-semibold mb-1">相似度热力图</h2>
      <p class="text-sm text-gray-500 mb-4">模块间代码相似度矩阵，颜色越深相似度越高</p>
      <div id="heatmap-container"></div>
    </div>
    <div class="bg-white rounded-xl shadow-sm border p-6">
      <h2 class="text-lg font-semibold mb-1">依赖关系图</h2>
      <p class="text-sm text-gray-500 mb-4">模块间克隆依赖关系力导向图</p>
      <svg id="force-graph" width="100%" height="500"></svg>
    </div>
  </div>
  <div class="bg-white rounded-xl shadow-sm border p-6">
    <h2 class="text-lg font-semibold mb-1">相似度分布</h2>
    <p class="text-sm text-gray-500 mb-4">所有模块对的相似度分布直方图</p>
    <div id="histogram-container"></div>
  </div>
</main>

<div id="tooltip" class="tooltip" style="display:none;"></div>

<script>
const DATA = {data_json};

function renderHeatmap() {{
  const container = document.getElementById('heatmap-container');
  const modules = DATA.modules;
  const matrix = DATA.similarity_matrix;
  const n = modules.length;
  if (n === 0 || n > 50) {{
    container.innerHTML = '<p class="text-gray-400 text-sm">模块数' + (n === 0 ? '为0' : '超过50，热力图已省略') + '</p>';
    return;
  }}

  const size = Math.min(500, container.clientWidth || 500);
  const margin = {{top: 80, right: 10, bottom: 10, left: 80}};
  const cellSize = (size - margin.left - margin.right) / n;

  const svg = d3.select(container).append('svg')
    .attr('width', size + margin.left + margin.right)
    .attr('height', size + margin.top + margin.bottom)
    .append('g').attr('transform', `translate(${{margin.left}},${{margin.top}})`);

  const colorScale = d3.scaleSequential(d3.interpolateYlOrRd).domain([0, 100]);

  const labels = svg.selectAll('.row-label')
    .data(modules).enter().append('text')
    .attr('class', 'row-label')
    .attr('x', -4).attr('y', (d, i) => i * cellSize + cellSize / 2)
    .attr('text-anchor', 'end').attr('dominant-baseline', 'middle')
    .attr('font-size', Math.max(8, 12 - n * 0.2) + 'px')
    .text(d => d.length > 20 ? d.slice(0, 17) + '...' : d);

  svg.selectAll('.col-label')
    .data(modules).enter().append('text')
    .attr('x', (d, i) => i * cellSize + cellSize / 2)
    .attr('y', -4).attr('text-anchor', 'start').attr('dominant-baseline', 'middle')
    .attr('transform', (d, i) => `rotate(-45,${{i * cellSize + cellSize / 2}},-4)`)
    .attr('font-size', Math.max(8, 12 - n * 0.2) + 'px')
    .text(d => d.length > 20 ? d.slice(0, 17) + '...' : d);

  const rows = svg.selectAll('.row')
    .data(matrix).enter().append('g')
    .attr('class', 'row')
    .attr('transform', (d, i) => `translate(0,${{i * cellSize}})`);

  rows.selectAll('.heatmap-cell')
    .data(d => d).enter().append('rect')
    .attr('class', 'heatmap-cell')
    .attr('x', (d, j) => j * cellSize)
    .attr('width', cellSize - 1).attr('height', cellSize - 1)
    .attr('rx', 2)
    .attr('fill', d => colorScale(d))
    .on('mouseover', function(event, d) {{
      const [i, j] = d3.select(this.parentNode).datum().__i !== undefined
        ? [d3.select(this.parentNode).datum().__i, 0]
        : [0, 0];
      const tooltip = document.getElementById('tooltip');
      tooltip.style.display = 'block';
      tooltip.style.left = event.pageX + 10 + 'px';
      tooltip.style.top = event.pageY + 10 + 'px';
      tooltip.textContent = `相似度: ${{d.toFixed(1)}}%`;
    }})
    .on('mouseout', () => {{
      document.getElementById('tooltip').style.display = 'none';
    }});

  const legend = d3.scaleLinear().domain([0, 100]).range([0, 120]);
  const legendBar = svg.append('g').attr('transform', `translate(${{n * cellSize + 20}},0)`);
  legendBar.selectAll('rect').data(d3.range(0, 100, 5)).enter().append('rect')
    .attr('x', 0).attr('y', d => legend(d))
    .attr('width', 12).attr('height', legend(5) - legend(0))
    .attr('fill', d => colorScale(d));
  legendBar.append('text').attr('x', 16).attr('y', 4).text('0%').attr('font-size', '10px');
  legendBar.append('text').attr('x', 16).attr('y', legend(100)).text('100%').attr('font-size', '10px');
}}

function renderForceGraph() {{
  const graph = DATA.dependency_graph;
  if (!graph.nodes.length) {{
    document.getElementById('force-graph').parentElement.innerHTML += '<p class="text-gray-400 text-sm">无依赖关系数据</p>';
    return;
  }}

  const svg = d3.select('#force-graph');
  const width = svg.node().parentElement.clientWidth || 500;
  const height = 500;
  svg.attr('width', width);

  const color = d3.scaleOrdinal(d3.schemeCategory10);
  const linkScale = d3.scaleLinear().domain([0, 100]).range([1, 6]).clamp(true);

  const simulation = d3.forceSimulation(graph.nodes)
    .force('link', d3.forceLink(graph.links).id(d => d.id).distance(d => 200 - d.value))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(30));

  const link = svg.append('g').selectAll('line')
    .data(graph.links).enter().append('line')
    .attr('stroke', '#999').attr('stroke-opacity', 0.6)
    .attr('stroke-width', d => linkScale(d.value));

  const node = svg.append('g').selectAll('g')
    .data(graph.nodes).enter().append('g').call(
      d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended)
    );

  node.append('circle').attr('r', 8).attr('fill', d => color(d.group))
    .attr('stroke', '#fff').attr('stroke-width', 2);

  node.append('text').attr('dx', 12).attr('dy', 4)
    .attr('font-size', '11px').text(d => d.name.length > 25 ? d.name.slice(0, 22) + '...' : d.name);

  simulation.on('tick', () => {{
    link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    node.attr('transform', d => `translate(${{d.x}},${{d.y}})`);
  }});

  function dragstarted(event) {{ if (!event.active) simulation.alphaTarget(0.3).restart(); event.subject.fx = event.subject.x; event.subject.fy = event.subject.y; }}
  function dragged(event) {{ event.subject.fx = event.x; event.subject.fy = event.y; }}
  function dragended(event) {{ if (!event.active) simulation.alphaTarget(0); event.subject.fx = null; event.subject.fy = null; }}
}}

function renderHistogram() {{
  const matrix = DATA.similarity_matrix;
  const n = matrix.length;
  const values = [];
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) values.push(matrix[i][j]);
  if (!values.length) {{
    document.getElementById('histogram-container').innerHTML = '<p class="text-gray-400 text-sm">无数据</p>';
    return;
  }}

  const container = document.getElementById('histogram-container');
  const width = container.clientWidth || 700;
  const margin = {{top: 10, right: 30, bottom: 40, left: 50}};
  const h = 250;
  const innerW = width - margin.left - margin.right;
  const innerH = h - margin.top - margin.bottom;

  const svg = d3.select(container).append('svg').attr('width', width).attr('height', h)
    .append('g').attr('transform', `translate(${{margin.left}},${{margin.top}})`);

  const x = d3.scaleLinear().domain([0, 100]).range([0, innerW]);
  const bins = d3.bin().domain(x.domain()).thresholds(20)(values);
  const y = d3.scaleLinear().domain([0, d3.max(bins, d => d.length)]).range([innerH, 0]);

  svg.selectAll('rect').data(bins).enter().append('rect')
    .attr('x', d => x(d.x0) + 1).attr('width', d => Math.max(0, x(d.x1) - x(d.x0) - 1))
    .attr('y', d => y(d.length)).attr('height', d => innerH - y(d.length))
    .attr('fill', d => d3.interpolateYlOrRd(d.x0 / 100)).attr('rx', 2);

  svg.append('g').attr('transform', `translate(0,${{innerH}})`).call(d3.axisBottom(x).ticks(10).tickFormat(d => d + '%'));
  svg.append('g').call(d3.axisLeft(y).ticks(5));
  svg.append('text').attr('x', innerW / 2).attr('y', innerH + 35).attr('text-anchor', 'middle').attr('font-size', '12px').text('相似度');
  svg.append('text').attr('transform', 'rotate(-90)').attr('x', -innerH / 2).attr('y', -35).attr('text-anchor', 'middle').attr('font-size', '12px').text('模块对数量');
}}

renderHeatmap();
renderForceGraph();
renderHistogram();
</script>
</body>
</html>"""
