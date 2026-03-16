#!/usr/bin/env python3
"""按产物名称从 industry_blueprints 中提取蓝图并导出 JSON 文件。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path("industry_blueprints.json")


def normalize_text(value: str) -> str:
    return value.casefold().strip()


def sanitize_filename(name: str) -> str:
    safe = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    return safe or "unnamed_product"


def parse_product_name(output_item: Any) -> str | None:
    if isinstance(output_item, str):
        return output_item
    if isinstance(output_item, dict):
        for key in ("name", "item", "product", "id"):
            value = output_item.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def extract_blueprints_container(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("industry_blueprints"), list):
            return payload["industry_blueprints"]
        # 兼容只有一个蓝图对象的情况
        return [payload]
    raise ValueError("JSON 内容不是可识别的蓝图结构。")


def find_matching_exports(blueprints: list[Any], product_keyword: str) -> list[tuple[str, Any]]:
    keyword = normalize_text(product_keyword)
    if not keyword:
        raise ValueError("产物名称不能为空。")

    exports: list[tuple[str, Any]] = []
    for blueprint in blueprints:
        if not isinstance(blueprint, dict):
            continue

        outputs = blueprint.get("outputs", [])
        if not isinstance(outputs, list):
            continue

        matched_products: set[str] = set()
        for output_item in outputs:
            product_name = parse_product_name(output_item)
            if not product_name:
                continue
            if keyword in normalize_text(product_name):
                matched_products.add(product_name.strip())

        for product in sorted(matched_products):
            exports.append((product, blueprint))

    return exports


def write_exports(exports: list[tuple[str, Any]], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    written_files: list[Path] = []
    name_counts: dict[str, int] = {}

    for product_name, blueprint in exports:
        base_name = f"{sanitize_filename(product_name)}_blueprint"
        count = name_counts.get(base_name, 0) + 1
        name_counts[base_name] = count

        filename = f"{base_name}.json" if count == 1 else f"{base_name}_{count}.json"
        target = output_dir / filename

        with target.open("w", encoding="utf-8") as f:
            json.dump(blueprint, f, ensure_ascii=False, indent=2)
            f.write("\n")

        written_files.append(target)

    return written_files


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"未找到数据文件: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="输入产物名称（支持部分匹配、不区分大小写），导出对应蓝图为 <产物名>_blueprint.json。"
    )
    parser.add_argument("keyword", nargs="?", help="要搜索的产物名称（部分即可）")
    parser.add_argument(
        "-s",
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"industry_blueprints 数据源文件路径（默认: {DEFAULT_SOURCE}）",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("."),
        help="导出目录（默认当前目录）",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    keyword = args.keyword or input("请输入产物名称（部分即可，不区分大小写）: ").strip()

    payload = load_json(args.source)
    blueprints = extract_blueprints_container(payload)
    exports = find_matching_exports(blueprints, keyword)

    if not exports:
        print("未找到匹配的蓝图。")
        return 0

    written_files = write_exports(exports, args.output_dir)
    print(f"已导出 {len(written_files)} 个蓝图文件：")
    for path in written_files:
        print(f"- {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
