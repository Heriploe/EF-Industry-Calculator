#!/usr/bin/env python3
"""按产物名称筛选 industry_blueprints 并导出蓝图 JSON。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
BLUEPRINTS_PATH = ROOT / "industry_blueprints.json"
TYPES_PATH = ROOT / "types.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_filename(name: str) -> str:
    sanitized = re.sub(r"[\\/:*?\"<>|]+", "_", name.strip())
    sanitized = re.sub(r"\s+", "_", sanitized)
    return sanitized or "blueprints"


def build_type_name_map(types_payload: Any) -> dict[int, str]:
    if isinstance(types_payload, dict) and isinstance(types_payload.get("data"), list):
        rows = types_payload["data"]
    elif isinstance(types_payload, list):
        rows = types_payload
    else:
        raise ValueError("types.json 格式不受支持")

    result: dict[int, str] = {}
    for row in rows:
        type_id = row.get("id")
        if type_id is None:
            continue
        result[int(type_id)] = row.get("name", "")
    return result


def enrich_items(items: list[dict[str, Any]], type_name_map: dict[int, str]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        copied = dict(item)
        type_id = copied.get("typeID")
        if type_id is not None:
            copied["name"] = type_name_map.get(int(type_id), "")
        enriched.append(copied)
    return enriched


def main() -> None:
    parser = argparse.ArgumentParser(description="按产物名称导出匹配蓝图")
    parser.add_argument("keyword", nargs="?", help="产物名称关键字（支持部分匹配，不区分大小写）")
    args = parser.parse_args()

    keyword = args.keyword or input("请输入产物名称关键字: ").strip()
    if not keyword:
        raise SystemExit("关键字不能为空")

    blueprints = load_json(BLUEPRINTS_PATH)
    type_name_map = build_type_name_map(load_json(TYPES_PATH))

    keyword_lower = keyword.lower()
    matched: list[dict[str, Any]] = []

    for blueprint_id, blueprint in blueprints.items():
        outputs = blueprint.get("outputs", [])
        output_names = [type_name_map.get(int(o.get("typeID", -1)), "") for o in outputs]
        if not any(keyword_lower in name.lower() for name in output_names if name):
            continue

        primary_type_id = blueprint.get("primaryTypeID")
        matched.append(
            {
                "blueprintID": int(blueprint_id),
                "primaryTypeID": primary_type_id,
                "primaryTypeName": type_name_map.get(int(primary_type_id), "") if primary_type_id is not None else "",
                "runTime": blueprint.get("runTime"),
                "inputs": enrich_items(blueprint.get("inputs", []), type_name_map),
                "outputs": enrich_items(outputs, type_name_map),
            }
        )

    if not matched:
        raise SystemExit(f"未找到产物名称包含“{keyword}”的蓝图")

    output_base_name = matched[0]["primaryTypeName"] if len(matched) == 1 and matched[0]["primaryTypeName"] else keyword
    output_path = ROOT / f"{normalize_filename(output_base_name)}_blueprint.json"

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(matched, f, ensure_ascii=False, indent=2)

    print(f"已导出 {len(matched)} 个蓝图到: {output_path.name}")


if __name__ == "__main__":
    main()
