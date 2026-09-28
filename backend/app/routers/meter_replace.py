"""换表记录接口：登记贸易结算表换表单，核对暂存项并维护唯一生效口径。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.meter_replace import STATUSES, MeterReplaceService

router = APIRouter(prefix="/api/meter_replace", tags=["换表记录"])

service = MeterReplaceService()

LIST_FIELDS = [
    "旧表编号", "新表编号", "表具类型", "口径规格", "安装位置",
    "旧表止度", "新表起度", "上期止度", "换表原因", "施工时间", "复核时间",
]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按旧表/新表编号或安装位置检索"),
    status: str | None = Query(default=None, description="暂存、生效"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """列出换表记录；止度回退、表号冲突或时间矛盾的记录停留在暂存。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出换表记录清单：返回全量数据，暂存记录同样可见以便核对。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "meter_replace", "total": total, "statuses": STATUSES, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条换表记录；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"换表记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记换表单；有核对项时先暂存并逐条提示，核对通过直接生效并同步档案。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if entry["status"] == "暂存":
        return ActionResult(
            ok=True,
            message="换表记录已暂存，请核对：" + "；".join(entry["警告"]),
            entry=entry,
        )
    return ActionResult(ok=True, message="换表记录已生效，水表档案已同步", entry=entry)


@router.post("/{entry_id}/review", response_model=ActionResult)
def review_entry(entry_id: int) -> ActionResult:
    """复核暂存记录：核对项全部消除后生效，并按该记录更新水表档案。"""
    entry, message = service.review_entry(entry_id)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=entry["status"] == "生效", message=message, entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """修改暂存记录；生效记录是档案与结算的共同口径，不能直接改动。"""
    entry, message = service.update_entry(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    warnings = entry.get("警告") or []
    detail = "，请核对：" + "；".join(warnings) if warnings else "，可复核生效"
    return ActionResult(ok=True, message=message + detail, entry=entry)


@router.delete("/{entry_id}", response_model=ActionResult)
def discard_entry(entry_id: int) -> ActionResult:
    """作废暂存记录；生效记录牵涉档案与结算，不允许作废。"""
    entry, message = service.discard_entry(entry_id)
    if entry is not None:
        return ActionResult(ok=True, message=message, entry=entry)
    return ActionResult(ok=False, message=message)
