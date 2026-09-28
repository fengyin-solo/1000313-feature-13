"""换表记录业务规则：止度回退、表号冲突、施工/复核时间核对都收在这里。

生效（status="生效"）的换表记录是唯一口径：水表档案按它更新，结算明细按它生成；
暂存（status="暂存"）的记录只留痕待核对，不影响档案与结算。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "meter_replace"
ARCHIVE_MODULE = "meter_record"

REQUIRED_FIELDS = [
    "旧表编号",
    "新表编号",
    "旧表止度",
    "新表起度",
    "施工时间",
    "复核时间",
    "换表原因",
]
ARCHIVE_FIELDS = ["表具类型", "口径规格", "安装位置"]

STATUS_DRAFT = "暂存"
STATUS_EFFECTIVE = "生效"
STATUSES = [STATUS_DRAFT, STATUS_EFFECTIVE]


def _to_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _find_archive(meter_no: str) -> dict[str, Any] | None:
    for row in store.rows(ARCHIVE_MODULE):
        if str(row.get("表具编号", "")).strip() == meter_no:
            return row
    return None


class MeterReplaceService:
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
                if keyword in str(row.get("旧表编号", ""))
                or keyword in str(row.get("新表编号", ""))
                or keyword in str(row.get("安装位置", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS:
            entry[field] = str(values.get(field)).strip()
        self._fill_archive_fields(entry)
        entry["警告"] = self._check_warnings(entry, exclude_id=None)
        entry["status"] = STATUS_DRAFT if entry["警告"] else STATUS_EFFECTIVE
        entry["pending"] = entry["status"] == STATUS_DRAFT
        entry["abnormal"] = bool(entry["警告"])
        rows.append(entry)
        self._apply_archive(entry)
        return entry, []

    def review_entry(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        """重新核对一条暂存记录：核对通过即生效，档案与结算口径随之更新。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"换表记录 {entry_id} 不存在或已归档"
        if entry.get("status") != STATUS_DRAFT:
            return None, "仅暂存记录需要核对生效"
        warnings = self._check_warnings(entry, exclude_id=entry_id)
        entry["警告"] = warnings
        if warnings:
            entry["abnormal"] = True
            return entry, "仍有核对项未消除，记录保持暂存：" + "；".join(warnings)
        entry["status"] = STATUS_EFFECTIVE
        entry["pending"] = False
        entry["abnormal"] = False
        self._apply_archive(entry)
        return entry, "核对通过，换表记录已生效并同步水表档案"

    def update_entry(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """编辑换表记录；生效记录是档案与结算的共同口径，不允许直接改动。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"换表记录 {entry_id} 不存在或已归档"
        if entry.get("status") != STATUS_DRAFT:
            return None, "生效记录已用于水表档案与结算明细，不能修改，请新建换表记录"
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        for field in REQUIRED_FIELDS:
            entry[field] = str(values.get(field)).strip()
        self._fill_archive_fields(entry)
        entry["警告"] = self._check_warnings(entry, exclude_id=entry_id)
        entry["abnormal"] = bool(entry["警告"])
        return entry, "暂存记录已更新，请核对后生效"

    def discard_entry(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        """作废一条暂存记录；生效记录牵涉档案与结算，不允许作废。"""
        rows = store.rows(MODULE)
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"换表记录 {entry_id} 不存在或已归档"
        if entry.get("status") != STATUS_DRAFT:
            return None, "生效记录已用于水表档案与结算明细，不能作废"
        rows.remove(entry)
        return None, "暂存的换表记录已作废"

    def latest_effective_map(self) -> dict[str, dict[str, Any]]:
        """按安装位置返回当前生效的换表记录，档案与结算共用这一份口径。"""
        latest: dict[str, dict[str, Any]] = {}
        for row in store.rows(MODULE):
            if row.get("status") != STATUS_EFFECTIVE:
                continue
            location = str(row.get("安装位置", "")).strip()
            current = latest.get(location)
            if current is None or int(row.get("id", 0)) > int(current.get("id", 0)):
                latest[location] = row
        return latest

    # ---- 内部规则 ------------------------------------------------------

    def _fill_archive_fields(self, entry: dict[str, Any]) -> None:
        """表具类型、口径规格、安装位置随旧表档案带出，保证三处描述一致。"""
        archive = _find_archive(entry["旧表编号"])
        for field in ARCHIVE_FIELDS:
            entry[field] = str(entry.get(field) or "").strip() or (
                str(archive.get(field, "")).strip() if archive else ""
            )
        entry["上期止度"] = str(archive.get("当前示数", "")).strip() if archive else ""

    def _check_warnings(self, entry: dict[str, Any], *, exclude_id: int | None) -> list[str]:
        warnings: list[str] = []

        old_no = entry["旧表编号"]
        new_no = entry["新表编号"]
        old_end = _to_float(entry.get("旧表止度"))
        new_start = _to_float(entry.get("新表起度"))
        built_at = _to_datetime(entry.get("施工时间"))
        reviewed_at = _to_datetime(entry.get("复核时间"))

        if old_end is None:
            warnings.append("旧表止度不是有效数字，请核对止度")
        if new_start is None:
            warnings.append("新表起度不是有效数字，请核对起度")

        archive = _find_archive(old_no)
        if archive is None:
            warnings.append(f"旧表编号「{old_no}」在水表档案中查不到，请核对表号")
        elif old_end is not None:
            # 止度回退：与档案当前示数比，也与上一条生效记录的旧表止度比
            baseline = _to_float(archive.get("当前示数"))
            prior = self._prior_effective(old_no)
            prior_end = _to_float(prior.get("旧表止度")) if prior else None
            if baseline is not None and old_end < baseline:
                warnings.append(
                    f"旧表止度 {old_end:g} 低于档案当前示数 {baseline:g}，疑似止度回退，请核对"
                )
            elif prior_end is not None and old_end < prior_end:
                warnings.append(
                    f"旧表止度 {old_end:g} 低于上次换表止度 {prior_end:g}，疑似止度回退，请核对"
                )

        # 表号冲突：新表号仍挂在档案上，或已被其他换表记录占用
        occupied = _find_archive(new_no)
        if occupied is not None and str(occupied.get("表具编号", "")).strip() != old_no:
            warnings.append(f"新表编号「{new_no}」与档案中在装表具冲突，请核对表号")
        else:
            for row in store.rows(MODULE):
                if exclude_id is not None and int(row.get("id", 0)) == exclude_id:
                    continue
                if str(row.get("新表编号", "")).strip() != new_no:
                    continue
                if str(row.get("旧表编号", "")).strip() == old_no:
                    continue
                warnings.append(f"新表编号「{new_no}」已被换表记录 #{row.get('id')} 占用，请核对表号")
                break

        if built_at is not None and reviewed_at is not None and built_at > reviewed_at:
            warnings.append("施工时间晚于复核时间，请核对时间")

        return warnings

    def _prior_effective(self, old_no: str) -> dict[str, Any] | None:
        """同一只表上一条生效记录（上一单的新表即本单旧表），用于止度连续核对。"""
        prior: dict[str, Any] | None = None
        for row in store.rows(MODULE):
            if row.get("status") != STATUS_EFFECTIVE:
                continue
            same_meter = (
                str(row.get("旧表编号", "")).strip() == old_no
                or str(row.get("新表编号", "")).strip() == old_no
            )
            if not same_meter:
                continue
            if prior is None or int(row.get("id", 0)) > int(prior.get("id", 0)):
                prior = row
        return prior

    def _apply_archive(self, entry: dict[str, Any]) -> None:
        """生效记录回写水表档案：换表页、档案、结算三处共用同一生效记录。"""
        if entry.get("status") != STATUS_EFFECTIVE:
            return
        archive = _find_archive(entry["旧表编号"])
        if archive is None:
            return
        archive["表具编号"] = entry["新表编号"]
        for field in ARCHIVE_FIELDS:
            if entry.get(field):
                archive[field] = entry[field]
        archive["上次示数"] = entry["旧表止度"]
        archive["当前示数"] = entry["新表起度"]
        archive["status"] = "正常"
        archive["pending"] = False
        archive["abnormal"] = False
        archive["生效换表单"] = entry["id"]
