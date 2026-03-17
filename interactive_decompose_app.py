#!/usr/bin/env python3
"""交互式分解界面：支持产物联想、数量输入、原料粘贴，并输出 Asteroid 需求。"""

from __future__ import annotations

import argparse
import json
import math
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from decompose_product_to_asteroid_csv import (
    DEFAULT_INVENTORY_PATH,
    PRODUCT_DIR,
    find_target_blueprint,
    fill_item_meta,
    load_inventory,
    load_json,
    load_recipes,
    load_types_maps,
    solve_integer_program,
)


def collect_product_names(name_map: dict[int, str], category_map: dict[int, str]) -> list[str]:
    names: set[str] = set()
    for product_path in sorted(PRODUCT_DIR.glob("*.json")):
        for blueprint in load_json(product_path):
            for output in blueprint.get("outputs", []):
                enriched = fill_item_meta(output, name_map, category_map)
                name = enriched.get("name", "").strip()
                if name:
                    names.add(name)
    return sorted(names)


def parse_inventory_text(raw_text: str, name_map: dict[int, str]) -> dict[int, int]:
    name_to_type: dict[str, int] = {name: type_id for type_id, name in name_map.items() if name}
    parsed: dict[int, int] = {}

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [segment.strip() for segment in line.replace(",", "\t").split("\t") if segment.strip()]
        if len(parts) < 2:
            continue

        item_name = parts[0]
        try:
            qty = int(parts[1])
        except ValueError:
            continue

        type_id = name_to_type.get(item_name)
        if type_id is None:
            continue
        parsed[type_id] = parsed.get(type_id, 0) + qty

    return parsed


def compute_asteroid_breakdown(product_name: str, required_quantity: int, pasted_inventory: str, refinery_file: str) -> dict[str, Any]:
    name_map, category_map = load_types_maps()
    base_inventory = load_inventory(Path(DEFAULT_INVENTORY_PATH), name_map)
    extra_inventory = parse_inventory_text(pasted_inventory, name_map)
    merged_inventory = dict(base_inventory)
    for type_id, qty in extra_inventory.items():
        merged_inventory[type_id] = merged_inventory.get(type_id, 0) + qty

    _, target_blueprint, target_output = find_target_blueprint(product_name, name_map, category_map)
    target_output_qty = int(target_output.get("quantity", 1)) or 1
    runs = max(1, math.ceil(required_quantity / target_output_qty))

    initial_state: dict[int, int] = {}
    for item in target_blueprint.get("inputs", []):
        enriched = fill_item_meta(item, name_map, category_map)
        type_id = int(enriched["typeID"])
        initial_state[type_id] = initial_state.get(type_id, 0) + int(enriched["quantity"]) * runs

    recipes = load_recipes(refinery_file, category_map)
    end_state, _ = solve_integer_program(initial_state, merged_inventory, recipes, category_map, overproduce_buffer=1)

    asteroid_totals = [
        {
            "name": name_map.get(type_id, ""),
            "quantity": qty,
        }
        for type_id, qty in end_state.items()
        if qty > 0 and category_map.get(type_id, "") == "Asteroid"
    ]
    asteroid_totals.sort(key=lambda row: row["name"])

    return {
        "requestedProduct": product_name,
        "requestedQuantity": required_quantity,
        "plannedRuns": runs,
        "singleRunOutput": target_output_qty,
        "actualOutput": runs * target_output_qty,
        "asteroids": asteroid_totals,
    }


def build_html(products: list[str]) -> str:
    products_json = json.dumps(products, ensure_ascii=False)
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Industry Decompose UI</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    .modal {{ position: fixed; inset: 0; background: rgba(0,0,0,.4); display: flex; align-items: center; justify-content: center; }}
    .card {{ background: #fff; border-radius: 8px; padding: 16px; width: min(92vw, 580px); }}
    input, textarea, button {{ font-size: 14px; width: 100%; box-sizing: border-box; margin-top: 8px; }}
    textarea {{ min-height: 240px; resize: vertical; overflow: auto; }}
    #result {{ margin-top: 16px; white-space: pre-wrap; background: #f7f7f7; padding: 12px; border-radius: 8px; }}
  </style>
</head>
<body>
  <h2>产物分解到 Asteroid</h2>

  <div id=\"productModal\" class=\"modal\">
    <div class=\"card\">
      <h3>输入产物与需求数量</h3>
      <input id=\"productInput\" list=\"productOptions\" placeholder=\"输入产物名称（可联想）\" />
      <datalist id=\"productOptions\"></datalist>
      <input id=\"quantityInput\" type=\"number\" min=\"1\" value=\"1\" placeholder=\"所需生产数量\" />
      <button id=\"confirmProduct\">确认</button>
    </div>
  </div>

  <section id=\"materialsSection\" style=\"display:none\">
    <p>可多次粘贴原料（每行: 名称\t数量 或 名称,数量）。输入框支持滚轮滚动和 Enter 换行。</p>
    <textarea id=\"materialsInput\" placeholder=\"例如:\nIron Ore\t120\nCopper Ore\t80\"></textarea>
    <button id=\"runBtn\">确认并计算</button>
  </section>

  <pre id=\"result\"></pre>

  <script>
    const products = {products_json};
    const optionBox = document.getElementById('productOptions');
    products.forEach(name => {{
      const option = document.createElement('option');
      option.value = name;
      optionBox.appendChild(option);
    }});

    const state = {{ productName: '', quantity: 1 }};

    document.getElementById('confirmProduct').addEventListener('click', () => {{
      const productName = document.getElementById('productInput').value.trim();
      const quantity = Number(document.getElementById('quantityInput').value || '1');
      if (!productName) {{
        alert('请先输入产物名称');
        return;
      }}
      if (!Number.isFinite(quantity) || quantity < 1) {{
        alert('数量需为正整数');
        return;
      }}
      state.productName = productName;
      state.quantity = Math.floor(quantity);
      document.getElementById('productModal').style.display = 'none';
      document.getElementById('materialsSection').style.display = 'block';
      document.getElementById('result').textContent = `已选择产物: ${{state.productName}}\n需求数量: ${{state.quantity}}`;
    }});

    document.getElementById('runBtn').addEventListener('click', async () => {{
      const pastedMaterials = document.getElementById('materialsInput').value;
      document.getElementById('result').textContent = '计算中...';
      const resp = await fetch('/api/decompose', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify({{
          productName: state.productName,
          quantity: state.quantity,
          materials: pastedMaterials,
        }}),
      }});
      const payload = await resp.json();
      if (!resp.ok) {{
        document.getElementById('result').textContent = `失败: ${{payload.error || 'unknown error'}}`;
        return;
      }}
      const lines = [
        `产物: ${{payload.requestedProduct}}`,
        `需求数量: ${{payload.requestedQuantity}}`,
        `计划执行次数: ${{payload.plannedRuns}} (单次产出 ${{payload.singleRunOutput}}，实际产出 ${{payload.actualOutput}})`,
        '',
        'Asteroid 需求:',
      ];
      if (!payload.asteroids.length) {{
        lines.push('  (无)');
      }} else {{
        payload.asteroids.forEach(row => lines.push(`- ${{row.name}}: ${{row.quantity}}`));
      }}
      document.getElementById('result').textContent = lines.join('\n');
    }});
  </script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    products: list[str] = []
    refinery_file: str = "refinery.json"

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/":
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        html = build_html(self.products).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/decompose":
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            product_name = str(payload.get("productName", "")).strip()
            quantity = int(payload.get("quantity", 1))
            materials = str(payload.get("materials", ""))
            if not product_name:
                raise ValueError("productName 不能为空")
            if quantity < 1:
                raise ValueError("quantity 必须 >= 1")
            result = compute_asteroid_breakdown(product_name, quantity, materials, self.refinery_file)
            self._send_json(result)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)


def main() -> None:
    parser = argparse.ArgumentParser(description="启动交互式产物分解页面")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--refinery", default="refinery.json", help="Refinery 文件名，默认 refinery.json")
    args = parser.parse_args()

    name_map, category_map = load_types_maps()
    Handler.products = collect_product_names(name_map, category_map)
    Handler.refinery_file = args.refinery

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"UI 已启动: http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
