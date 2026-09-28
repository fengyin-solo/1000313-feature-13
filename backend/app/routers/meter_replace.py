"""换表记录接口：登记、暂存核对、生效流转，并向水表档案与结算明细提供同一生效记录。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.meter_replace import MeterReplaceService

router = APIRouter(prefix="/api/meter_replace", tags=["换表记录"])

service = MeterReplaceService()

LIST_FIELDS = [
    "换表编号",
    "旧表编号",
    "新表编号",
    "表具类型",
    "口径规格",
    "安装位置",
    "旧表止度",
    "新表起度",
    "换表原因",
    "施工时间",
    "复核时间",
    "施工人员",
    "状态",
    "核对提示",
]
STATUSES = ["暂存", "生效"]


@router.get("/settlements", response_model=PageResult[dict])
def list_settlements() -> PageResult[dict]:
    """结算明细：只取生效换表记录，与换表页、水表档案共用同一条。"""
    items = service.list_settlements()
    return PageResult(items=items, total=len(items), page=1, size=len(items) or 1)


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按换表编号、旧表编号、新表编号检索"),
    status: str | None = Query(default=None, description="暂存、生效"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按表号与状态过滤换表记录；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出换表记录清单：暂存与生效全量返回。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "meter_replace", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条换表记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"换表记录 {entry_id} 不存在")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记换表记录：止度回退、表号冲突或施工晚于复核时只暂存并提示核对。"""
    entry, missing, error = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    if entry is None:
        return ActionResult(ok=False, message=error)
    return ActionResult(ok=True, message=error, entry=entry)


@router.put("/{entry_id}", response_model=ActionResult)
def update_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """核对修改暂存记录并重新校验；生效记录锁定，不允许改动。"""
    entry, message = service.update_entry(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对暂存换表记录执行核对生效；仍有核对项时继续暂存并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    if action != "核对生效":
        return ActionResult(ok=False, message=f"动作「{action}」不属于换表记录可执行范围")
    entry, message = service.promote_entry(entry_id)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
