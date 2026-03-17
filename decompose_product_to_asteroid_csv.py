#!/usr/bin/env python3
"""按产物名称递归分解至 Asteroid，并导出 CSV（使用整数规划搜索最小 Asteroid 总量）。"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PRODUCT_DIR = ROOT / "Product"
PRINTER_DIR = ROOT / "Printer"
REFINERY_DIR = ROOT / "Refinery"
TYPES_PATH = ROOT / "types.json"
DEFAULT_INVENTORY_PATH = ROOT / "Inventory" / "inventory.csv"


class DecomposeError(RuntimeError):
    pass


@dataclass(frozen=True)
class Recipe:
    blueprint_id: int
    source: str
    inputs: tuple[tuple[int, int], ...]
    outputs: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class BranchChoice:
    recipe_index: int
    runs: int


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_filename(name: str) -> str:
    sanitized = re.sub(r"[\\/:*?\"<>|]+", "_", name.strip())
    sanitized = re.sub(r"\s+", "_", sanitized)
    return sanitized or "asteroid_breakdown"


def load_types_maps() -> tuple[dict[int, str], dict[int, str]]:
    payload = load_json(TYPES_PATH)
    rows = payload.get("data", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
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


def load_inventory(path: Path, name_map: dict[int, str]) -> dict[int, int]:
    if not path.exists():
        raise DecomposeError(f"库存文件不存在：{path}")

    name_to_type: dict[str, int] = {}
    for type_id, name in name_map.items():
        key = name.strip()
        if key and key not in name_to_type:
            name_to_type[key] = type_id

    inventory: dict[int, int] = {}
    with path.open("r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 2:
                continue
            item_name = row[0].strip()
            quantity_text = row[1].strip()
            if not item_name or not quantity_text:
                continue

            try:
                quantity = int(quantity_text)
            except ValueError:
                continue

            type_id = name_to_type.get(item_name)
            if type_id is None:
                continue

            inventory[type_id] = inventory.get(type_id, 0) + quantity

    return inventory


def fill_item_meta(item: dict[str, Any], name_map: dict[int, str], category_map: dict[int, str]) -> dict[str, Any]:
    copied = dict(item)
    if copied.get("typeID") is None:
        return copied
    type_id = int(copied["typeID"])
    copied["typeID"] = type_id
    copied["quantity"] = int(copied.get("quantity", 0))
    copied["name"] = copied.get("name") or name_map.get(type_id, "")
    copied["categoryName"] = copied.get("categoryName") or category_map.get(type_id, "")
    return copied


def find_target_blueprint(product_name: str, name_map: dict[int, str], category_map: dict[int, str]) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    for product_path in sorted(PRODUCT_DIR.glob("*.json")):
        for blueprint in load_json(product_path):
            for output in blueprint.get("outputs", []):
                enriched = fill_item_meta(output, name_map, category_map)
                if enriched.get("name") == product_name:
                    return product_path, blueprint, enriched
    raise DecomposeError(f"未在 Product 中找到产物：{product_name}")


def load_recipes(refinery_file: str, category_map: dict[int, str]) -> list[Recipe]:
    refinery_path = REFINERY_DIR / refinery_file
    if not refinery_path.exists():
        raise DecomposeError(f"指定的 Refinery 文件不存在：{refinery_file}")

    recipes: list[Recipe] = []
    source_files = [refinery_path, *sorted(PRINTER_DIR.glob("*.json"))]
    for source in source_files:
        for bp in load_json(source):
            inputs = tuple((int(i["typeID"]), int(i.get("quantity", 0))) for i in bp.get("inputs", []) if i.get("typeID") is not None)
            outputs = tuple((int(o["typeID"]), int(o.get("quantity", 0))) for o in bp.get("outputs", []) if o.get("typeID") is not None)
            if not inputs or not outputs:
                continue
            # 仅保留“向上生产”配方（输出不是 Asteroid），避免与反向分解配方形成环
            if any(category_map.get(out_type, "") == "Asteroid" for out_type, _ in outputs):
                continue
            recipes.append(
                Recipe(
                    blueprint_id=int(bp.get("blueprintID", 0)),
                    source=source.name,
                    inputs=inputs,
                    outputs=outputs,
                )
            )
    return recipes


def state_to_key(state: dict[int, int]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted((k, v) for k, v in state.items() if v != 0))


def apply_choice(state: dict[int, int], recipe: Recipe, runs: int) -> dict[int, int]:
    next_state = dict(state)
    for type_id, qty in recipe.inputs:
        next_state[type_id] = next_state.get(type_id, 0) + qty * runs
    for type_id, qty in recipe.outputs:
        next_state[type_id] = next_state.get(type_id, 0) - qty * runs
    return next_state


def choose_next_item(state: dict[int, int], producible_non_asteroid: set[int]) -> int | None:
    candidates = [t for t, q in state.items() if q > 0 and t in producible_non_asteroid]
    if not candidates:
        return None
    return max(candidates, key=lambda t: state[t])


def solve_integer_program(
    initial_state: dict[int, int],
    initial_inventory: dict[int, int],
    recipes: list[Recipe],
    category_map: dict[int, str],
    overproduce_buffer: int,
    preferred_recipe_sources: set[str] | None = None,
) -> tuple[dict[int, int], list[BranchChoice]]:
    output_to_recipes: dict[int, list[int]] = {}
    producible_non_asteroid: set[int] = set()
    for idx, recipe in enumerate(recipes):
        for type_id, _ in recipe.outputs:
            output_to_recipes.setdefault(type_id, []).append(idx)
            if category_map.get(type_id, "") != "Asteroid":
                producible_non_asteroid.add(type_id)

    preferred_sources = preferred_recipe_sources or set()

    def consume_inventory_once(state: dict[int, int], inventory: dict[int, int], type_id: int) -> tuple[dict[int, int], dict[int, int]]:
        demand = state.get(type_id, 0)
        available = inventory.get(type_id, 0)
        if demand <= 0 or available <= 0:
            return state, inventory

        consumed = min(demand, available)
        next_state = dict(state)
        next_inventory = dict(inventory)
        next_state[type_id] = demand - consumed
        next_inventory[type_id] = available - consumed
        return next_state, next_inventory

    def consume_terminal_inventory(state: dict[int, int], inventory: dict[int, int]) -> tuple[dict[int, int], dict[int, int]]:
        next_state = dict(state)
        next_inventory = dict(inventory)
        for type_id, demand in list(next_state.items()):
            if demand <= 0:
                continue
            available = next_inventory.get(type_id, 0)
            if available <= 0:
                continue
            consumed = min(demand, available)
            next_state[type_id] = demand - consumed
            next_inventory[type_id] = available - consumed
        return next_state, next_inventory

    @lru_cache(maxsize=None)
    def solve(
        state_key: tuple[tuple[int, int], ...],
        inventory_key: tuple[tuple[int, int], ...],
    ) -> tuple[tuple[int, int, int, int], tuple[BranchChoice, ...], tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
        state = dict(state_key)
        inventory = dict(inventory_key)

        next_item = choose_next_item(state, producible_non_asteroid)
        if next_item is not None:
            reduced_state, reduced_inventory = consume_inventory_once(state, inventory, next_item)
            if reduced_state != state:
                return solve(state_to_key(reduced_state), state_to_key(reduced_inventory))

        if next_item is None:
            state, inventory = consume_terminal_inventory(state, inventory)
            asteroid_total = sum(q for t, q in state.items() if q > 0 and category_map.get(t, "") == "Asteroid")
            skipped_total = sum(q for t, q in state.items() if q > 0 and category_map.get(t, "") != "Asteroid" and t not in producible_non_asteroid)
            return (asteroid_total, skipped_total, 0, 0), tuple(), state_to_key(state), state_to_key(inventory)

        best_obj: tuple[int, int, int, int] | None = None
        best_plan: tuple[BranchChoice, ...] = tuple()
        best_end_state = state_key
        best_end_inventory = inventory_key

        candidate_recipe_indices = output_to_recipes.get(next_item, [])
        if preferred_sources:
            preferred_candidates = [idx for idx in candidate_recipe_indices if recipes[idx].source in preferred_sources]
            if preferred_candidates:
                candidate_recipe_indices = preferred_candidates

        for recipe_idx in candidate_recipe_indices:
            recipe = recipes[recipe_idx]
            out_qty = next((qty for t, qty in recipe.outputs if t == next_item), 0)
            if out_qty <= 0:
                continue

            demand_qty = state.get(next_item, 0)
            min_runs = (demand_qty + out_qty - 1) // out_qty
            max_runs = min_runs + overproduce_buffer

            for runs in range(min_runs, max_runs + 1):
                child_state = apply_choice(state, recipe, runs)
                child_obj, child_plan, child_end_state, child_end_inventory = solve(state_to_key(child_state), state_to_key(inventory))
                non_preferred_runs = 0 if not preferred_sources or recipe.source in preferred_sources else runs
                current_obj = (child_obj[0], child_obj[1], child_obj[2] + non_preferred_runs, child_obj[3] + runs)
                if best_obj is None or current_obj < best_obj:
                    best_obj = current_obj
                    best_plan = (BranchChoice(recipe_idx, runs),) + child_plan
                    best_end_state = child_end_state
                    best_end_inventory = child_end_inventory

        if best_obj is None:
            # 无可用配方，强制结束（该物料会在终态按 skipped 统计）
            state, inventory = consume_terminal_inventory(state, inventory)
            asteroid_total = sum(q for t, q in state.items() if q > 0 and category_map.get(t, "") == "Asteroid")
            skipped_total = sum(q for t, q in state.items() if q > 0 and category_map.get(t, "") != "Asteroid" and t not in producible_non_asteroid)
            return (asteroid_total, skipped_total, 0, 0), tuple(), state_to_key(state), state_to_key(inventory)

        return best_obj, best_plan, best_end_state, best_end_inventory

    _, best_plan, end_state_key, _ = solve(state_to_key(initial_state), state_to_key(initial_inventory))
    return dict(end_state_key), list(best_plan)


def write_csv(output_path: Path, product_name: str, product_output_quantity: int, asteroid_totals: dict[int, int], name_map: dict[int, str]) -> None:
    rows = []
    for type_id, quantity in sorted(asteroid_totals.items(), key=lambda x: (name_map.get(x[0], ""), x[0])):
        rows.append(
            {
                "productName": product_name,
                "productOutputQuantity": str(product_output_quantity),
                "asteroidTypeID": str(type_id),
                "asteroidName": name_map.get(type_id, ""),
                "requiredQuantity": str(quantity),
                "categoryName": "Asteroid",
            }
        )

    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["productName", "productOutputQuantity", "asteroidTypeID", "asteroidName", "requiredQuantity", "categoryName"],
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="将 Product 中指定产物分解至 Asteroid，并使用整数规划最小化 Asteroid 总量")
    parser.add_argument("product_name", help="Product 中要分解的产物名称（精确匹配）")
    parser.add_argument("--refinery", default="refinery.json", help="Refinery 文件名，默认 refinery.json")
    parser.add_argument("--output", help="输出 CSV 路径，默认 <产物名>_asteroid_breakdown.csv")
    parser.add_argument("--overproduce-buffer", type=int, default=1, help="整数规划搜索时允许的额外过量生产缓冲，默认 1")
    parser.add_argument("--inventory", default=str(DEFAULT_INVENTORY_PATH), help="库存 CSV 路径，默认 Inventory/inventory.csv")
    args = parser.parse_args()

    name_map, category_map = load_types_maps()
    inventory = load_inventory(Path(args.inventory), name_map)
    product_path, target_blueprint, target_output = find_target_blueprint(args.product_name, name_map, category_map)
    recipes = load_recipes(args.refinery, category_map)

    initial_state: dict[int, int] = {}
    for item in target_blueprint.get("inputs", []):
        enriched = fill_item_meta(item, name_map, category_map)
        type_id = int(enriched["typeID"])
        initial_state[type_id] = initial_state.get(type_id, 0) + int(enriched["quantity"])

    preferred_sources = {"field_printer.json"} if args.refinery == "field_refinery.json" else None
    end_state, plan = solve_integer_program(
        initial_state, inventory, recipes, category_map, max(0, args.overproduce_buffer), preferred_recipe_sources=preferred_sources
    )

    asteroid_totals = {t: q for t, q in end_state.items() if q > 0 and category_map.get(t, "") == "Asteroid"}
    skipped_totals = {
        t: q
        for t, q in end_state.items()
        if q > 0 and category_map.get(t, "") != "Asteroid" and all(t != out_t for r in recipes for out_t, _ in r.outputs)
    }

    output_path = Path(args.output) if args.output else ROOT / f"{normalize_filename(args.product_name)}_asteroid_breakdown.csv"
    write_csv(output_path, args.product_name, int(target_output.get("quantity", 1)), asteroid_totals, name_map)

    print(f"已从 {product_path.name} 找到产物：{args.product_name}")
    print(f"使用 Refinery：{args.refinery}")
    print(f"使用 Inventory：{args.inventory}")
    print(f"整数规划步骤数：{len(plan)}")
    print(f"最小 Asteroid 总量：{sum(asteroid_totals.values())}")
    print(f"已导出分解结果：{output_path}")

    if skipped_totals:
        print("以下原料无法在指定 Refinery + Printer 中继续分解，已跳过：")
        for type_id, qty in sorted(skipped_totals.items(), key=lambda x: (name_map.get(x[0], ""), x[0])):
            print(f"- {name_map.get(type_id, '')}({type_id}): {qty}")


if __name__ == "__main__":
    main()
