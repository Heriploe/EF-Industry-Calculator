#!/usr/bin/env python3
"""提取 Product 目录下蓝图所需原料的对应蓝图。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PRODUCT_DIR = ROOT / "Product"
BLUEPRINTS_PATH = ROOT / "industry_blueprints.json"
TYPES_PATH = ROOT / "types.json"
OUTPUT_PATH = "material_blueprints.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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


def enrich_items(items: list[dict[str, Any]], name_map: dict[int, str]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        copied = dict(item)
        type_id = copied.get("typeID")
        if type_id is not None:
            copied["name"] = name_map.get(int(type_id), "")
        enriched.append(copied)
    return enriched


def read_product_blueprints() -> list[dict[str, Any]]:
    blueprints: list[dict[str, Any]] = []
    for path in sorted(PRODUCT_DIR.glob("*.json")):
        if path.name == OUTPUT_PATH.name:
            continue
        payload = load_json(path)
        if not isinstance(payload, list):
            continue
        for row in payload:
            if not isinstance(row, dict):
                continue
            row_copy = dict(row)
            row_copy["sourceFile"] = path.name
            blueprints.append(row_copy)
    return blueprints


def build_output_index(industry_blueprints: dict[str, dict[str, Any]]) -> dict[int, list[tuple[int, dict[str, Any]]]]:
    output_index: dict[int, list[tuple[int, dict[str, Any]]]] = {}
    for blueprint_id, blueprint in industry_blueprints.items():
        for output in blueprint.get("outputs", []):
            type_id = output.get("typeID")
            if type_id is None:
                continue
            output_index.setdefault(int(type_id), []).append((int(blueprint_id), blueprint))
    return output_index


def main() -> None:
    product_blueprints = read_product_blueprints()
    industry_blueprints: dict[str, dict[str, Any]] = load_json(BLUEPRINTS_PATH)
    type_name_map = build_type_name_map(load_json(TYPES_PATH))
    output_index = build_output_index(industry_blueprints)

    seen_blueprint_ids: set[int] = set()
    extracted: list[dict[str, Any]] = []

    for product_blueprint in product_blueprints:
        for item in product_blueprint.get("inputs", []):
            type_id = item.get("typeID")
            if type_id is None:
                continue

            for blueprint_id, material_blueprint in output_index.get(int(type_id), []):
                if blueprint_id in seen_blueprint_ids:
                    continue

                primary_type_id = material_blueprint.get("primaryTypeID")
                extracted.append(
                    {
                        "blueprintID": blueprint_id,
                        "primaryTypeID": primary_type_id,
                        "primaryTypeName": type_name_map.get(int(primary_type_id), "")
                        if primary_type_id is not None
                        else "",
                        "runTime": material_blueprint.get("runTime"),
                        "inputs": enrich_items(material_blueprint.get("inputs", []), type_name_map),
                        "outputs": enrich_items(material_blueprint.get("outputs", []), type_name_map),
                    }
                )
                seen_blueprint_ids.add(blueprint_id)

    extracted.sort(key=lambda row: row["blueprintID"])

    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(extracted, f, ensure_ascii=False, indent=2)

    print(f"已提取 {len(extracted)} 个原料蓝图到: {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
