#!/usr/bin/env python3
"""提取所有非中间产物蓝图的原料（去重）。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
BLUEPRINTS_PATH = ROOT / "industry_blueprints.json"
TYPES_PATH = ROOT / "types.json"


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

    type_name_map: dict[int, str] = {}
    for row in rows:
        type_id = row.get("id")
        if type_id is not None:
            type_name_map[int(type_id)] = row.get("name", "")
    return type_name_map


def get_final_product_type_id(blueprint: dict[str, Any]) -> int | None:
    primary_type_id = blueprint.get("primaryTypeID")
    if primary_type_id is not None:
        return int(primary_type_id)

    outputs = blueprint.get("outputs", [])
    if outputs and outputs[0].get("typeID") is not None:
        return int(outputs[0]["typeID"])
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="提取非中间产物蓝图对应原料（去重）")
    parser.add_argument(
        "-o",
        "--output",
        default="non_intermediate_materials.json",
        help="导出文件名（默认: non_intermediate_materials.json）",
    )
    args = parser.parse_args()

    blueprints: dict[str, dict[str, Any]] = load_json(BLUEPRINTS_PATH)
    type_name_map = build_type_name_map(load_json(TYPES_PATH))

    all_input_type_ids: set[int] = set()
    for blueprint in blueprints.values():
        for input_item in blueprint.get("inputs", []):
            type_id = input_item.get("typeID")
            if type_id is not None:
                all_input_type_ids.add(int(type_id))

    selected_blueprints: list[dict[str, Any]] = []
    unique_material_ids: set[int] = set()

    for blueprint_id, blueprint in blueprints.items():
        final_product_type_id = get_final_product_type_id(blueprint)
        if final_product_type_id is None:
            continue

        if final_product_type_id in all_input_type_ids:
            continue

        material_ids: list[int] = []
        for input_item in blueprint.get("inputs", []):
            type_id = input_item.get("typeID")
            if type_id is None:
                continue
            material_id = int(type_id)
            material_ids.append(material_id)
            unique_material_ids.add(material_id)

        selected_blueprints.append(
            {
                "blueprintID": int(blueprint_id),
                "finalProductTypeID": final_product_type_id,
                "finalProductName": type_name_map.get(final_product_type_id, ""),
                "materialTypeIDs": material_ids,
                "materials": [
                    {"typeID": material_id, "name": type_name_map.get(material_id, "")}
                    for material_id in material_ids
                ],
            }
        )

    unique_materials = [
        {"typeID": material_id, "name": type_name_map.get(material_id, "")}
        for material_id in sorted(unique_material_ids)
    ]

    output_data = {
        "nonIntermediateBlueprintCount": len(selected_blueprints),
        "uniqueMaterialCount": len(unique_materials),
        "uniqueMaterials": unique_materials,
        "blueprints": selected_blueprints,
    }

    output_path = ROOT / args.output
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"已识别 {len(selected_blueprints)} 个非中间产物蓝图")
    print(f"去重后原料数量: {len(unique_materials)}")
    print(f"导出文件: {output_path.name}")


if __name__ == "__main__":
    main()
