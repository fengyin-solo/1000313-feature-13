"""换表记录业务规则：止度回退、表号冲突、施工晚于复核三类核对点，
以及"暂存—核对—生效"的流转都收在这里。

生效记录是换表页、水表档案、结算明细三处的唯一事实来源：
暂存记录不回写档案、不进结算；只有核对生效时才联动水表档案并投影到结算明细。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "meter_replace"
METER_MODULE = "meter_record"

REQUIRED_FIELDS = [
    "旧表编号",
    "新表编号",
    "旧表止度",
    "新表起度",
    "换表原因",
    "施工时间",
    "复核时间",
    "施工人员",
]
IDENTITY_FIELDS = ["表具类型", "口径规格", "安装位置"]

EFFECTIVE = "生效"
DRAFT = "暂存"
STATUS_ORDER = [DRAFT, EFFECTIVE]

WARNING_ROLLBACK = "旧表止度低于档案当前示数，疑似止度回退，请核对后再生效"
WARNING_NEW_CONFLICT = "新表编号与水表档案中的在装表号冲突，请核对后再生效"
WARNING_REPLACE_CONFLICT = "该表已有生效换表记录，不能重复换表，请核对后再生效"
WARNING_TIME_ORDER = "施工时间晚于复核时间，请核对后再生效"

_TIME_FORMATS = ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"]


def _parse_time(value: Any) -> datetime | None:
    """兼容日期、日期时分、datetime-local（T 分隔）三种录入形式。"""
    text = str(value).strip() if value is not None else ""
    if not text:
        return None
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_reading(value: Any) -> float | None:
    """表计示度只接受非负数字。"""
    text = str(value).strip() if value is not None else ""
    if not text:
        return None
    try:
        reading = float(text)
    except ValueError:
        return None
    return reading if reading >= 0 else None


def _format_reading(reading: float) -> float | int:
    return int(reading) if reading.is_integer() else round(reading, 2)


class MeterReplaceService:
    # ---------- 查询 ----------
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("换表编号", ""))
                or keyword in str(row.get("旧表编号", ""))
                or keyword in str(row.get("新表编号", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def list_settlements(self) -> list[dict[str, Any]]:
        """结算明细只投影生效记录，保证与换表页、水表档案同一条记录。"""
        settlements: list[dict[str, Any]] = []
        for row in store.rows(MODULE):
            if row.get("status") != EFFECTIVE:
                continue
            start_reading = row.get("新表起度")
            stop_reading = row.get("旧表止度")
            consumption: Any = "—"
            if isinstance(start_reading, (int, float)) and isinstance(stop_reading, (int, float)):
                consumption = _format_reading(float(stop_reading) - float(start_reading))
            settlements.append(
                {
                    "换表编号": row.get("换表编号"),
                    "表具编号": row.get("新表编号"),
                    "表具类型": row.get("表具类型"),
                    "口径规格": row.get("口径规格"),
                    "安装位置": row.get("安装位置"),
                    "旧表编号": row.get("旧表编号"),
                    "旧表止度": stop_reading,
                    "新表起度": start_reading,
                    "换表期用量": consumption,
                    "换表原因": row.get("换表原因"),
                    "施工时间": row.get("施工时间"),
                    "复核时间": row.get("复核时间"),
                }
            )
        return settlements

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    # ---------- 写入 ----------
    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], str]:
        """登记换表记录。校验通过直接生效并联动档案；不通过则暂存并附核对提示。

        返回 (记录, 缺失字段, 硬错误说明)。记录的 status/核对提示 描述核对结果。
        """
        missing = [
            field
            for field in REQUIRED_FIELDS
            if not str(values.get(field) if values.get(field) is not None else "").strip()
        ]
        if missing:
            return None, missing, ""

        old_meter = self._find_meter(values.get("旧表编号"))
        if old_meter is None:
            return None, [], f"旧表 {values.get('旧表编号')} 不在水表档案中，请先建档后再登记换表"

        old_stop = _parse_reading(values.get("旧表止度"))
        new_start = _parse_reading(values.get("新表起度"))
        if old_stop is None or new_start is None:
            return None, [], "旧表止度、新表起度必须是非负数字"
        if _parse_time(values.get("施工时间")) is None or _parse_time(values.get("复核时间")) is None:
            return None, [], "施工时间、复核时间格式不正确，应为 年-月-日 时:分"

        entry = self._build_entry(values, old_meter, old_stop, new_start)
        store.rows(MODULE).append(entry)
        if entry["status"] == EFFECTIVE:
            self._apply_to_archive(entry)
            return entry, [], "换表记录核对通过，已生效并同步水表档案与结算明细"
        return entry, [], "换表记录存在核对项，已暂存，请核对后再生效"

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """暂存记录核对修改后重新校验；生效记录不允许改动，保证三处引用稳定。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"换表记录 {entry_id} 不存在"
        if entry["status"] != DRAFT:
            return None, "生效记录不允许修改，如需更正请登记新的换表记录"

        merged = {**entry, **values}
        missing = [
            field
            for field in REQUIRED_FIELDS
            if not str(merged.get(field) if merged.get(field) is not None else "").strip()
        ]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        old_meter = self._find_meter(merged.get("旧表编号"))
        if old_meter is None:
            return None, f"旧表 {merged.get('旧表编号')} 不在水表档案中，请先建档后再登记换表"
        old_stop = _parse_reading(merged.get("旧表止度"))
        new_start = _parse_reading(merged.get("新表起度"))
        if old_stop is None or new_start is None:
            return None, "旧表止度、新表起度必须是非负数字"
        if _parse_time(merged.get("施工时间")) is None or _parse_time(merged.get("复核时间")) is None:
            return None, "施工时间、复核时间格式不正确，应为 年-月-日 时:分"

        for field in REQUIRED_FIELDS + IDENTITY_FIELDS:
            if field in merged:
                entry[field] = merged[field]
        entry["旧表止度"] = _format_reading(old_stop)
        entry["新表起度"] = _format_reading(new_start)
        entry["施工时间"] = self._normalize_time(merged.get("施工时间"))
        entry["复核时间"] = self._normalize_time(merged.get("复核时间"))
        self._fill_identity(entry, old_meter, merged)
        entry["核对提示"] = self._check_warnings(entry, exclude_id=None)
        return entry, "暂存记录已更新并重新核对，确认无误后可生效"

    def promote_entry(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        """暂存记录复核生效：再次跑全部核对点，通过才联动档案。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"换表记录 {entry_id} 不存在"
        if entry["status"] == EFFECTIVE:
            return None, "该换表记录已生效，无需重复核对"
        warnings = self._check_warnings(entry, exclude_id=None)
        if warnings:
            entry["核对提示"] = warnings
            return None, "核对未通过：" + "；".join(warnings)
        entry["status"] = EFFECTIVE
        entry["pending"] = False
        entry["核对提示"] = []
        self._apply_to_archive(entry)
        return entry, "换表记录已核对生效，水表档案与结算明细已同步"

    # ---------- 内部规则 ----------
    def _build_entry(
        self,
        values: dict[str, Any],
        old_meter: dict[str, Any],
        old_stop: float,
        new_start: float,
    ) -> dict[str, Any]:
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["换表编号"] = f"CHGB-{entry['id']:04d}"
        for field in REQUIRED_FIELDS:
            entry[field] = values.get(field)
        entry["旧表止度"] = _format_reading(old_stop)
        entry["新表起度"] = _format_reading(new_start)
        entry["施工时间"] = self._normalize_time(values.get("施工时间"))
        entry["复核时间"] = self._normalize_time(values.get("复核时间"))
        self._fill_identity(entry, old_meter, values)
        warnings = self._check_warnings(entry, exclude_id=None)
        entry["status"] = DRAFT if warnings else EFFECTIVE
        entry["pending"] = bool(warnings)
        entry["abnormal"] = False
        entry["核对提示"] = warnings
        return entry

    def _fill_identity(
        self, entry: dict[str, Any], old_meter: dict[str, Any], values: dict[str, Any]
    ) -> None:
        """表具类型、口径规格、安装位置以水表档案旧表为准，表单只作补录兜底。"""
        for field in IDENTITY_FIELDS:
            override = str(values.get(field) if values.get(field) is not None else "").strip()
            entry[field] = override or old_meter.get(field)

    def _check_warnings(self, entry: dict[str, Any], exclude_id: int | None) -> list[str]:
        """三类核对点，任一命中即只能暂存。exclude_id 用于跳过自身。"""
        warnings: list[str] = []

        old_meter = self._find_meter(entry.get("旧表编号"))
        current_reading = _parse_reading(old_meter.get("当前示数")) if old_meter else None
        old_stop = _parse_reading(entry.get("旧表止度"))
        if (
            old_meter is not None
            and current_reading is not None
            and old_stop is not None
            and old_stop < current_reading
        ):
            warnings.append(WARNING_ROLLBACK)

        new_no = str(entry.get("新表编号") or "").strip()
        old_no = str(entry.get("旧表编号") or "").strip()
        if self._find_meter(new_no) is not None:
            warnings.append(WARNING_NEW_CONFLICT)
        else:
            # 旧表首次换表时匹配旧表编号；换过之后档案表号已更新为新表编号，
            # 同一位置再次换表会以"上一次的新表号"作为旧表号，两种都要拦下。
            for row in store.rows(MODULE):
                if exclude_id is not None and int(row.get("id", 0)) == exclude_id:
                    continue
                if row.get("status") != EFFECTIVE:
                    continue
                if old_no in (
                    str(row.get("旧表编号", "")).strip(),
                    str(row.get("新表编号", "")).strip(),
                ):
                    warnings.append(WARNING_REPLACE_CONFLICT)
                    break

        built_at = _parse_time(entry.get("施工时间"))
        checked_at = _parse_time(entry.get("复核时间"))
        if built_at is not None and checked_at is not None and built_at > checked_at:
            warnings.append(WARNING_TIME_ORDER)

        return warnings

    def _apply_to_archive(self, entry: dict[str, Any]) -> None:
        """生效后联动水表档案：档案直接换为新表号，旧表止度留痕。
        档案上的换表编号与结算明细都指向这一条生效记录。
        """
        meter = self._find_meter(entry.get("旧表编号"))
        if meter is None:
            return
        meter["表具编号"] = entry["新表编号"]
        meter["表具类型"] = entry.get("表具类型")
        meter["口径规格"] = entry.get("口径规格")
        meter["安装位置"] = entry.get("安装位置")
        meter["上次示数"] = entry.get("新表起度")
        meter["当前示数"] = entry.get("新表起度")
        meter["表具状态"] = "正常"
        meter["status"] = "正常"
        meter["pending"] = False
        meter["abnormal"] = False
        meter["最近换表"] = entry.get("换表编号")
        meter["旧表止度"] = entry.get("旧表止度")

    def _find_meter(self, meter_no: Any) -> dict[str, Any] | None:
        target = str(meter_no).strip() if meter_no is not None else ""
        if not target:
            return None
        for row in store.rows(METER_MODULE):
            if str(row.get("表具编号", "")).strip() == target:
                return row
        return None

    def _normalize_time(self, value: Any) -> str:
        parsed = _parse_time(value)
        if parsed is None:
            return str(value).strip() if value is not None else ""
        if len(str(value).strip()) <= 10:
            return parsed.strftime("%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d %H:%M")
