"""贸易结算明细接口：只读，数据全部来自生效的换表记录。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import PageResult
from app.services.meter_settlement import MeterSettlementService

router = APIRouter(prefix="/api/meter_settlement", tags=["贸易结算"])

service = MeterSettlementService()


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按表号、安装位置或结算编号检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """列出由生效换表记录派生的结算明细；暂存记录不参与结算。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出结算明细：全量生效记录，供财务核对。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "meter_settlement", "total": total, "items": items}
