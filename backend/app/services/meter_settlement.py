"""贸易结算明细：不允许单独登记，全部由生效的换表记录派生。

结算页、换表页、水表档案因此天然共用同一份生效记录，不会出现各算各的口径。
暂存的换表记录不参与结算。
"""
from __future__ import annotations

from typing import Any

from app.services.meter_replace import _to_float
from app.store import store

MODULE = "meter_replace"
ARCHIVE_MODULE = "meter_record"


class MeterSettlementService:
    def build_entry(self, record: dict[str, Any]) -> dict[str, Any]:
        """由一条生效换表记录算出结算明细；算不出用量时标注待核对而不是瞎算。"""
        old_end = _to_float(record.get("旧表止度"))
        prior_end = _to_float(record.get("上期止度"))
        if old_end is not None and prior_end is not None:
            quantity = old_end - prior_end
            note = "止度回退，请核对" if quantity < 0 else ""
        else:
            quantity = None
            note = "缺少上期止度，用量待核对"
        archive_no = ""
        for row in store.rows(ARCHIVE_MODULE):
            if int(row.get("生效换表单") or 0) == int(record.get("id", 0)):
                archive_no = str(row.get("表具编号", ""))
                break
        return {
            "id": int(record.get("id", 0)),
            "结算编号": f"SETT-{int(record.get('id', 0)):04d}",
            "生效换表单": int(record.get("id", 0)),
            "表具类型": record.get("表具类型", ""),
            "口径规格": record.get("口径规格", ""),
            "安装位置": record.get("安装位置", ""),
            "旧表编号": record.get("旧表编号", ""),
            "新表编号": record.get("新表编号", ""),
            "在装表号": archive_no or record.get("新表编号", ""),
            "上期止度": prior_end,
            "旧表止度": old_end,
            "结算用量": quantity,
            "换表原因": record.get("换表原因", ""),
            "施工时间": record.get("施工时间", ""),
            "复核时间": record.get("复核时间", ""),
            "核对说明": note,
        }

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [
            self.build_entry(row)
            for row in store.rows(MODULE)
            if row.get("status") == "生效"
        ]
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("旧表编号", ""))
                or keyword in str(row.get("新表编号", ""))
                or keyword in str(row.get("安装位置", ""))
                or keyword in str(row.get("结算编号", ""))
            ]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total
