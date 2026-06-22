"""
MkDocs Material 文档配置生成器

生成mkdocs.yml配置和docs目录结构。
MkDocs Material是最佳文档主题之一。

Author: ModuleMirror
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


MKDOCS_YML_TEMPLATE = """site_name: ModuleMirror - GitHub代码相似度检测器
site_description: GitHub项目代码相似度查重工具，用于自我审视和抄袭溯源
site_author: ModuleMirror Team
site_url: https://github.com/ModuleMirror/gh-similarity-detector

repo_name: ModuleMirror/gh-similarity-detector
repo_url: https://github.com/ModuleMirror/gh-similarity-detector
edit_uri: edit/main/docs/

theme:
  name: material
  language: zh
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: 切换到暗色模式
    - scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: 切换到亮色模式
  features:
    - navigation.instant
    - navigation.tracking
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - navigation.indexes
    - navigation.top
    - search.suggest
    - search.highlight
    - search.share
    - toc.follow
    - content.code.copy
    - content.code.annotate
  icon:
    repo: fontawesome/brands/github

plugins:
  - search:
      lang: 
        - zh
        - en
  - git-revision-date-localized:
      enable_creation_date: true
      type: datetime
  - minify:
      minify_html: true

markdown_extensions:
  - abbr
  - admonition
  - attr_list
  - codehilite
  - def_list
  - footnotes
  - md_in_html
  - toc:
      permalink: true
  - pymdownx.arithmatex:
      generic: true
  - pymdownx.betterem:
      smart_enable: all
  - pymdownx.caret
  - pymdownx.details
  - pymdownx.emoji:
      emoji_index: !!python/name:material.extensions.emoji.twemoji
      emoji_generator: !!python/name:material.extensions.emoji.to_svg
  - pymdownx.highlight:
      anchor_linenums: true
      line_spans: __span
      pygments_lang_class: true
  - pymdownx.inlinehilite
  - pymdownx.keys
  - pymdownx.mark
  - pymdownx.smartsymbols
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.code_format
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.tasklist:
      custom_checkbox: true
  - pymdownx.tilde

nav:
  - 首页: index.md
  - 快速开始: 
    - installation.md
    - quickstart.md
  - 用户指南:
    - cli.md
    - api.md
    - configuration.md
    - examples.md
  - 核心功能:
    - fingerprint.md
    - similarity.md
    - rules.md
    - reports.md
  - 高级特性:
    - lsh-index.md
    - cross-language.md
    - visualization.md
    - realtime-progress.md
  - 开发文档:
    - architecture.md
    - contributing.md
    - testing.md
    - performance.md
  - API参考:
    - api-reference/core.md
    - api-reference/infrastructure.md
    - api-reference/cli.md
  - 更新日志: changelog.md
"""

INDEX_MD = """# ModuleMirror

<p align="center">
  <img src="assets/logo.png" alt="ModuleMirror Logo" width="200">
</p>

**GitHub项目代码相似度查重工具**

用于**自我审视**（发现可复用代码）和**抄袭溯源**（追溯代码来源）。

## 核心特性

- ⚡ **Winnowing指纹算法** - 高效代码指纹提取
- 🌳 **AST结构指纹** - 跨语言结构相似性检测
- 📊 **多种相似度算法** - Jaccard、余弦相似度、编辑距离
- 🗄️ **SQLite持久化** - 指纹库增量更新
- 🔍 **YAML规则引擎** - 自定义检测规则
- 📈 **MinHash LSH** - 大规模快速近似检索
- 🎨 **交互式可视化** - PyEcharts热力图、网络图
- ⚙️ **实时进度推送** - SSE Server-Sent Events

## 快速开始

```bash
# 安装
pip install gh-similarity-detector

# 基础检测
gh-sim detect /path/to/repo

# 对比两个仓库
gh-sim compare repo1 repo2

# 生成可视化报告
gh-sim detect /path/to/repo --report html
```

## 架构

```mermaid
graph TD
    A[代码仓库] --> B[解析器 tree-sitter]
    B --> C[AST提取]
    B --> D[Token提取]
    C --> E[结构指纹]
    D --> F[Winnowing指纹]
    E --> G[相似度计算]
    F --> G
    G --> H[SQLite存储]
    G --> I[报告生成]
```

## 许可证

MIT License
"""

INSTALLATION_MD = """# 安装指南

## 系统要求

- Python 3.9+
- SQLite 3.35+

## 基础安装

```bash
pip install gh-similarity-detector
```

## 可选依赖

```bash
# 可视化增强
pip install gh-similarity-detector[visualization-enhanced]

# 实时进度推送
pip install gh-similarity-detector[realtime]

# 向量索引
pip install gh-similarity-detector[vector-index]

# 所有语言支持
pip install gh-similarity-detector[all-languages]

# 全部功能
pip install gh-similarity-detector[all]
```

## 验证安装

```bash
gh-sim --version
gh-sim --help
```
"""


def generate_mkdocs_config(
    output_dir: str = "docs",
    overwrite: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    files_created = {}

    mkdocs_yml = output.parent / "mkdocs.yml"
    if overwrite or not mkdocs_yml.exists():
        mkdocs_yml.write_text(MKDOCS_YML_TEMPLATE, encoding="utf-8")
        files_created["mkdocs.yml"] = str(mkdocs_yml)

    docs_structure = {
        "index.md": INDEX_MD,
        "installation.md": INSTALLATION_MD,
    }

    for filename, content in docs_structure.items():
        filepath = output / filename
        if overwrite or not filepath.exists():
            filepath.write_text(content, encoding="utf-8")
            files_created[filename] = str(filepath)

    placeholder_docs = [
        "quickstart.md",
        "cli.md",
        "api.md",
        "configuration.md",
        "examples.md",
        "fingerprint.md",
        "similarity.md",
        "rules.md",
        "reports.md",
        "lsh-index.md",
        "cross-language.md",
        "visualization.md",
        "realtime-progress.md",
        "architecture.md",
        "contributing.md",
        "testing.md",
        "performance.md",
        "changelog.md",
    ]

    for filename in placeholder_docs:
        filepath = output / filename
        if overwrite or not filepath.exists():
            title = filename.replace(".md", "").replace("-", " ").title()
            filepath.write_text(f"# {title}\n\nTODO: 编写内容\n", encoding="utf-8")
            files_created[filename] = str(filepath)

    api_ref_dir = output / "api-reference"
    api_ref_dir.mkdir(exist_ok=True)

    for filename in ["core.md", "infrastructure.md", "cli.md"]:
        filepath = api_ref_dir / filename
        if overwrite or not filepath.exists():
            filepath.write_text(
                f"# API参考 - {filename.replace('.md', '').title()}\n\nTODO\n",
                encoding="utf-8",
            )
            files_created[f"api-reference/{filename}"] = str(filepath)

    assets_dir = output / "assets"
    assets_dir.mkdir(exist_ok=True)

    return files_created
