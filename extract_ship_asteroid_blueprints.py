#!/usr/bin/env python3
"""提取船只产物蓝图与含小行星原料蓝图。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
BLUEPRINTS_PATH = ROOT / "industry_blueprints.json"
TYPES_PATH = ROOT / "types.json"
SHIP_OUTPUT_PATH = ROOT / "ship.json"
ASTEROID_INPUT_PATH = ROOT / "asteroid.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_type_maps(types_payload: Any) -> tuple[dict[int, str], dict[int, str]]:
    if isinstance(types_payload, dict) and isinstance(types_payload.get("data"), list):
        rows = types_payload["data"]
    elif isinstance(types_payload, list):
        rows = types_payload
    else:
        raise ValueError("types.json 格式不受支持")

    name_map: dict[int, str] = {}
    category_map: dict[int, str] = {}

    for row in rows:
        type_id = row.get("id")
        if type_id is None:
            continue
        normalized_id = int(type_id)
        name_map[normalized_id] = row.get("name", "")
        category_map[normalized_id] = row.get("categoryName", "")

    return name_map, category_map


def enrich_items(items: list[dict[str, Any]], name_map: dict[int, str], category_map: dict[int, str]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        copied = dict(item)
        type_id = copied.get("typeID")
        if type_id is not None:
            normalized_id = int(type_id)
            copied["name"] = name_map.get(normalized_id, "")
            copied["categoryName"] = category_map.get(normalized_id, "")
        enriched.append(copied)
    return enriched


def is_ship_output(blueprint: dict[str, Any], category_map: dict[int, str]) -> bool:
    for output in blueprint.get("outputs", []):
        type_id = output.get("typeID")
        if type_id is None:
            continue
        if category_map.get(int(type_id)) == "Ship":
            return True
    return False


def has_asteroid_input(blueprint: dict[str, Any], category_map: dict[int, str]) -> bool:
    for input_item in blueprint.get("inputs", []):
        type_id = input_item.get("typeID")
        if type_id is None:
            continue
        if category_map.get(int(type_id)) == "Asteroid":
            return True
    return False


def format_blueprint(
    blueprint_id: str,
    blueprint: dict[str, Any],
    name_map: dict[int, str],
    category_map: dict[int, str],
) -> dict[str, Any]:
    primary_type_id = blueprint.get("primaryTypeID")
    primary_name = ""
    primary_category = ""
    if primary_type_id is not None:
        normalized_primary_type_id = int(primary_type_id)
        primary_name = name_map.get(normalized_primary_type_id, "")
        primary_category = category_map.get(normalized_primary_type_id, "")

    return {
        "blueprintID": int(blueprint_id),
        "primaryTypeID": primary_type_id,
        "primaryTypeName": primary_name,
        "primaryCategoryName": primary_category,
        "runTime": blueprint.get("runTime"),
        "inputs": enrich_items(blueprint.get("inputs", []), name_map, category_map),
        "outputs": enrich_items(blueprint.get("outputs", []), name_map, category_map),
    }


def main() -> None:
    blueprints: dict[str, dict[str, Any]] = load_json(BLUEPRINTS_PATH)
    name_map, category_map = build_type_maps(load_json(TYPES_PATH))

    ship_blueprints: list[dict[str, Any]] = []
    asteroid_blueprints: list[dict[str, Any]] = []

    for blueprint_id, blueprint in blueprints.items():
        formatted = format_blueprint(blueprint_id, blueprint, name_map, category_map)
        if is_ship_output(blueprint, category_map):
            ship_blueprints.append(formatted)
        if has_asteroid_input(blueprint, category_map):
            asteroid_blueprints.append(formatted)

    with SHIP_OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(ship_blueprints, f, ensure_ascii=False, indent=2)

    with ASTEROID_INPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(asteroid_blueprints, f, ensure_ascii=False, indent=2)

    print(f"ship.json 已导出 {len(ship_blueprints)} 个蓝图")
    print(f"asteroid.json 已导出 {len(asteroid_blueprints)} 个蓝图")


if __name__ == "__main__":
    main()
