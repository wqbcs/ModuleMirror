"""报告路由"""

import json
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from pathlib import Path

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
async def list_reports(
    report_dir: str = Query(default="./report"),
):
    """列出所有检测报告"""
    rdir = Path(report_dir).resolve()
    if not rdir.exists():
        return {"reports": []}
    reports = []
    for f in sorted(rdir.rglob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.suffix in ('.html', '.json', '.md'):
            reports.append({
                'name': f.name,
                'path': str(f.relative_to(rdir)),
                'size': f.stat().st_size,
                'modified': f.stat().st_mtime,
            })
    return {"reports": reports, "total": len(reports)}


def _safe_report_path(report_dir: str, report_id: str) -> Path:
    rdir = Path(report_dir).resolve()
    target = (rdir / Path(report_id).name).resolve()
    if not str(target).startswith(str(rdir)):
        raise HTTPException(status_code=400, detail="非法路径")
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"报告不存在: {report_id}")
    return target


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    report_dir: str = Query(default="./report"),
):
    """获取报告内容"""
    target = _safe_report_path(report_dir, report_id)
    if target.suffix == '.json':
        with open(target, 'r', encoding='utf-8') as f:
            return json.load(f)
    elif target.suffix in ('.html', '.md'):
        content = target.read_text(encoding='utf-8')
        if target.suffix == '.html':
            return HTMLResponse(content=content)
        return PlainTextResponse(content=content)
    raise HTTPException(status_code=400, detail=f"不支持的报告格式: {target.suffix}")


@router.get("/{report_id}/summary")
async def get_report_summary(
    report_id: str,
    report_dir: str = Query(default="./report"),
):
    """获取报告摘要"""
    target = _safe_report_path(report_dir, report_id)
    if target.suffix == '.json':
        with open(target, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return {
                'total_results': len(data),
                'total_matches': sum(r.get('match_count', 0) for r in data if isinstance(r, dict)),
            }
        return data
    return {"path": str(target), "size": target.stat().st_size}


@router.get("/visual/latest")
async def get_visual_report(
    report_dir: str = Query(default="./report"),
):
    """获取最新的可视化报告(D3.js热力图+依赖图)"""
    rdir = Path(report_dir).resolve()
    for f in sorted(rdir.glob("visual_report*.html"), key=lambda p: p.stat().st_mtime, reverse=True):
        content = f.read_text(encoding="utf-8")
        return HTMLResponse(content=content)
    raise HTTPException(status_code=404, detail="可视化报告不存在，请先执行检测生成报告")
