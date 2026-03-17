#!/usr/bin/env python3
"""按产物名称递归分解至 Asteroid，并导出 CSV（不可分解原料会跳过）。"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PRODUCT_DIR = ROOT / "Product"
PRINTER_DIR = ROOT / "Printer"
REFINERY_DIR = ROOT / "Refinery"
TYPES_PATH = ROOT / "types.json"


class DecomposeError(RuntimeError):
    """无法完成分解时抛出的错误。"""


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_filename(name: str) -> str:
    sanitized = re.sub(r"[\\/:*?\"<>|]+", "_", name.strip())
    sanitized = re.sub(r"\s+", "_", sanitized)
    return sanitized or "asteroid_breakdown"


def load_types_maps() -> tuple[dict[int, str], dict[int, str]]:
    payload = load_json(TYPES_PATH)
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        rows = payload["data"]
    elif isinstance(payload, list):
        rows = payload
    else:
        raise DecomposeError("types.json 格式不受支持")

    name_map: dict[int, str] = {}
    category_map: dict[int, str] = {}
    for row in rows:
        type_id = row.get("id")
        if type_id is None:
            continue
        normalized = int(type_id)
        name_map[normalized] = row.get("name", "")
        category_map[normalized] = row.get("categoryName", "")
    return name_map, category_map


def fill_item_meta(item: dict[str, Any], name_map: dict[int, str], category_map: dict[int, str]) -> dict[str, Any]:
    copied = dict(item)
    type_id = copied.get("typeID")
    if type_id is None:
        return copied

    normalized = int(type_id)
    copied["typeID"] = normalized
    copied["name"] = copied.get("name") or name_map.get(normalized, "")
    copied["categoryName"] = copied.get("categoryName") or category_map.get(normalized, "")
    copied["quantity"] = int(copied.get("quantity", 0))
    return copied


def find_target_blueprint(product_name: str, name_map: dict[int, str], category_map: dict[int, str]) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    product_files = sorted(PRODUCT_DIR.glob("*.json"))
    if not product_files:
        raise DecomposeError("Product 文件夹下未找到任何 JSON 文件")

    for product_path in product_files:
        blueprints = load_json(product_path)
        for blueprint in blueprints:
            outputs = blueprint.get("outputs", [])
            for output in outputs:
                enriched = fill_item_meta(output, name_map, category_map)
                if enriched.get("name") == product_name:
                    return product_path, blueprint, enriched

    raise DecomposeError(f"未在 Product 中找到产物：{product_name}")


def build_recipe_index(refinery_file: str, name_map: dict[int, str], category_map: dict[int, str]) -> dict[int, tuple[dict[str, Any], dict[str, Any]]]:
    recipes: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}

    refinery_path = REFINERY_DIR / refinery_file
    if not refinery_path.exists():
        raise DecomposeError(f"指定的 Refinery 文件不存在：{refinery_file}")

    source_files = [refinery_path, *sorted(PRINTER_DIR.glob("*.json"))]
    for source in source_files:
        for blueprint in load_json(source):
            outputs = blueprint.get("outputs", [])
            for output in outputs:
                enriched_output = fill_item_meta(output, name_map, category_map)
                type_id = enriched_output.get("typeID")
                if type_id is None:
                    continue
                if type_id in recipes:
                    continue
                normalized_blueprint = {
                    "blueprintID": blueprint.get("blueprintID"),
                    "inputs": [fill_item_meta(item, name_map, category_map) for item in blueprint.get("inputs", [])],
                    "outputs": [fill_item_meta(item, name_map, category_map) for item in outputs],
                }
                recipes[type_id] = (normalized_blueprint, enriched_output)
    return recipes


def decompose_to_asteroid(
    item: dict[str, Any],
    recipes: dict[int, tuple[dict[str, Any], dict[str, Any]]],
    accum: dict[int, Fraction],
    skipped: dict[int, Fraction],
    name_map: dict[int, str],
    category_map: dict[int, str],
    stack: set[int],
) -> None:
    type_id = int(item["typeID"])
    category = item.get("categoryName") or category_map.get(type_id, "")
    quantity = Fraction(item["quantity"])

    if category == "Asteroid":
        accum[type_id] += quantity
        return

    recipe_entry = recipes.get(type_id)
    if recipe_entry is None:
        skipped[type_id] += quantity
        return

    if type_id in stack:
        raise DecomposeError(f"检测到循环分解：{type_id}")

    blueprint, recipe_output = recipe_entry
    output_qty = int(recipe_output.get("quantity", 0))
    if output_qty <= 0:
        raise DecomposeError(f"蓝图 {blueprint.get('blueprintID')} 的产出数量无效")

    runs = quantity / Fraction(output_qty)
    stack.add(type_id)
    try:
        for input_item in blueprint["inputs"]:
            next_item = dict(input_item)
            next_item["quantity"] = Fraction(int(input_item["quantity"])) * runs
            decompose_to_asteroid(next_item, recipes, accum, skipped, name_map, category_map, stack)
    finally:
        stack.remove(type_id)


def fraction_to_str(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


def write_csv(
    output_path: Path,
    product_name: str,
    product_output_quantity: int,
    asteroid_totals: dict[int, Fraction],
    name_map: dict[int, str],
) -> None:
    rows: list[dict[str, str]] = []
    for type_id, quantity in sorted(asteroid_totals.items(), key=lambda x: (name_map.get(x[0], ""), x[0])):
        rows.append(
            {
                "productName": product_name,
                "productOutputQuantity": str(product_output_quantity),
                "asteroidTypeID": str(type_id),
                "asteroidName": name_map.get(type_id, ""),
                "requiredQuantity": fraction_to_str(quantity),
                "categoryName": "Asteroid",
            }
        )

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "productName",
                "productOutputQuantity",
                "asteroidTypeID",
                "asteroidName",
                "requiredQuantity",
                "categoryName",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="将 Product 中指定产物递归分解至 Asteroid 并导出 CSV")
    parser.add_argument("product_name", help="Product 中要分解的产物名称（需精确匹配）")
    parser.add_argument("--refinery", default="refinery.json", help="Refinery 文件名，默认 refinery.json")
    parser.add_argument("--output", help="输出 CSV 路径，默认 <产物名>_asteroid_breakdown.csv")
    args = parser.parse_args()

    name_map, category_map = load_types_maps()
    product_path, target_blueprint, target_output = find_target_blueprint(args.product_name, name_map, category_map)
    recipes = build_recipe_index(args.refinery, name_map, category_map)

    asteroid_totals: dict[int, Fraction] = defaultdict(Fraction)
    skipped_totals: dict[int, Fraction] = defaultdict(Fraction)
    for input_item in target_blueprint.get("inputs", []):
        enriched = fill_item_meta(input_item, name_map, category_map)
        decompose_to_asteroid(enriched, recipes, asteroid_totals, skipped_totals, name_map, category_map, set())

    output_path = Path(args.output) if args.output else ROOT / f"{normalize_filename(args.product_name)}_asteroid_breakdown.csv"
    write_csv(output_path, args.product_name, int(target_output.get("quantity", 1)), asteroid_totals, name_map)

    print(f"已从 {product_path.name} 找到产物：{args.product_name}")
    print(f"使用 Refinery：{args.refinery}")
    print(f"已导出分解结果：{output_path}")
    if skipped_totals:
        print("以下原料无法在指定 Refinery + Printer 中继续分解，已跳过：")
        for type_id, qty in sorted(skipped_totals.items(), key=lambda x: (name_map.get(x[0], ""), x[0])):
            print(f"- {name_map.get(type_id, '')}({type_id}): {fraction_to_str(qty)}")


if __name__ == "__main__":
    main()
