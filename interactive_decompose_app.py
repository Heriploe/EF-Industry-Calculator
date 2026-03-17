#!/usr/bin/env python3
"""Tkinter 交互式分解界面。"""

from __future__ import annotations

import argparse
import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from decompose_product_to_asteroid_csv import (
    PRODUCT_DIR,
    find_target_blueprint,
    fill_item_meta,
    load_json,
    load_recipes,
    load_types_maps,
    solve_integer_program,
)

CACHE_PATH = Path(__file__).resolve().parent / "Inventory" / "inventory_cache.json"

I18N: dict[str, dict[str, str]] = {
    "zh": {
        "title": "产物分解工具",
        "materials_label": "原料输入 可多次粘贴 支持滚轮和换行",
        "use_cache": "使用缓存库存",
        "pick_product": "选择产物",
        "settings": "设置",
        "compute": "确认并计算",
        "product_dialog_title": "输入产物和数量",
        "product_name": "产物名称",
        "suggestions": "联想下拉",
        "quantity": "生产数量",
        "confirm": "确认",
        "error": "错误",
        "calc_fail": "计算失败",
        "need_product": "请先输入产物名称",
        "invalid_product": "产物不存在",
        "invalid_qty": "数量必须是正整数",
        "need_select": "请先选择产物和数量",
        "selected": "已选择产物",
        "demand": "需求数量",
        "ready": "请粘贴库存后点击确认并计算",
        "result_title": "分解结果",
        "runs": "执行次数",
        "run_output": "单次产出",
        "actual_output": "实际产出",
        "asteroid_list": "Asteroid 名称及个数",
        "none": "无",
        "settings_title": "设置",
        "language": "语言",
        "chinese": "中文",
        "english": "English",
        "save": "保存",
        "cache_notice": "已使用缓存库存",
    },
    "en": {
        "title": "Product Decompose Tool",
        "materials_label": "Material input paste multiple times scroll and newline supported",
        "use_cache": "Use cached inventory",
        "pick_product": "Select product",
        "settings": "Settings",
        "compute": "Confirm and run",
        "product_dialog_title": "Input product and quantity",
        "product_name": "Product name",
        "suggestions": "Suggestion dropdown",
        "quantity": "Quantity",
        "confirm": "Confirm",
        "error": "Error",
        "calc_fail": "Calculation failed",
        "need_product": "Please input product name",
        "invalid_product": "Product not found",
        "invalid_qty": "Quantity must be positive integer",
        "need_select": "Please select product and quantity",
        "selected": "Selected product",
        "demand": "Required quantity",
        "ready": "Paste inventory then confirm and run",
        "result_title": "Decompose result",
        "runs": "Runs",
        "run_output": "Output per run",
        "actual_output": "Actual output",
        "asteroid_list": "Asteroid name and count",
        "none": "None",
        "settings_title": "Settings",
        "language": "Language",
        "chinese": "中文",
        "english": "English",
        "save": "Save",
        "cache_notice": "Cached inventory used",
    },
}


def collect_product_names(name_map: dict[int, str], category_map: dict[int, str]) -> list[str]:
    names: set[str] = set()
    for product_path in sorted(PRODUCT_DIR.glob("*.json")):
        for blueprint in load_json(product_path):
            for output in blueprint.get("outputs", []):
                enriched = fill_item_meta(output, name_map, category_map)
                product_name = enriched.get("name", "").strip()
                if product_name:
                    names.add(product_name)
    return sorted(names)


def parse_inventory_text(raw_text: str, name_map: dict[int, str]) -> dict[int, int]:
    name_to_type = {name: type_id for type_id, name in name_map.items() if name}
    inventory: dict[int, int] = {}

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.replace(",", "\t").split("\t") if part.strip()]
        if len(parts) < 2:
            continue

        item_name = parts[0]
        try:
            quantity = int(parts[1])
        except ValueError:
            continue

        type_id = name_to_type.get(item_name)
        if type_id is None:
            continue
        inventory[type_id] = inventory.get(type_id, 0) + quantity

    return inventory


def compute_asteroids(product_name: str, required_quantity: int, inventory_text: str, refinery_file: str) -> dict[str, Any]:
    name_map, category_map = load_types_maps()
    inventory = parse_inventory_text(inventory_text, name_map)

    _, target_blueprint, target_output = find_target_blueprint(product_name, name_map, category_map)
    output_qty = int(target_output.get("quantity", 1)) or 1
    runs = max(1, math.ceil(required_quantity / output_qty))

    initial_state: dict[int, int] = {}
    for item in target_blueprint.get("inputs", []):
        enriched = fill_item_meta(item, name_map, category_map)
        type_id = int(enriched["typeID"])
        initial_state[type_id] = initial_state.get(type_id, 0) + int(enriched["quantity"]) * runs

    recipes = load_recipes(refinery_file, category_map)
    end_state, _ = solve_integer_program(initial_state, inventory, recipes, category_map, overproduce_buffer=1)

    asteroids = [
        (name_map.get(type_id, ""), quantity)
        for type_id, quantity in end_state.items()
        if quantity > 0 and category_map.get(type_id, "") == "Asteroid"
    ]
    asteroids.sort(key=lambda row: row[0])

    return {
        "requested_product": product_name,
        "requested_quantity": required_quantity,
        "planned_runs": runs,
        "single_run_output": output_qty,
        "actual_output": runs * output_qty,
        "asteroids": asteroids,
    }


class App:
    def __init__(self, root: tk.Tk, refinery_file: str):
        self.root = root
        self.refinery_file = refinery_file
        self.name_map, self.category_map = load_types_maps()
        self.products = collect_product_names(self.name_map, self.category_map)

        self.language = "zh"
        self.product_name = ""
        self.required_quantity = 1
        self.use_cache_var = tk.BooleanVar(value=False)

        self.materials_label: tk.Label | None = None
        self.cache_check: tk.Checkbutton | None = None
        self.pick_btn: tk.Button | None = None
        self.settings_btn: tk.Button | None = None
        self.compute_btn: tk.Button | None = None
        self.status_label: tk.Label | None = None
        self.materials_text: tk.Text | None = None

        self.root.geometry("760x560")
        self._build_main_window()
        self._apply_language()
        self._show_product_dialog()

    def tr(self, key: str) -> str:
        return I18N[self.language][key]

    def _build_main_window(self) -> None:
        frame = tk.Frame(self.root, padx=12, pady=12)
        frame.pack(fill=tk.BOTH, expand=True)

        self.materials_label = tk.Label(frame)
        self.materials_label.pack(anchor="w")

        self.cache_check = tk.Checkbutton(frame, variable=self.use_cache_var)
        self.cache_check.pack(anchor="w", pady=(4, 8))

        text_wrapper = tk.Frame(frame)
        text_wrapper.pack(fill=tk.BOTH, expand=True)

        self.materials_text = tk.Text(text_wrapper, wrap=tk.NONE)
        self.materials_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        y_scroll = tk.Scrollbar(text_wrapper, orient=tk.VERTICAL, command=self.materials_text.yview)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.materials_text.configure(yscrollcommand=y_scroll.set)

        x_scroll = tk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.materials_text.xview)
        x_scroll.pack(fill=tk.X)
        self.materials_text.configure(xscrollcommand=x_scroll.set)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(8, 8))

        self.pick_btn = tk.Button(btn_frame, command=self._show_product_dialog)
        self.pick_btn.pack(side=tk.LEFT)

        self.settings_btn = tk.Button(btn_frame, command=self._open_settings)
        self.settings_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.compute_btn = tk.Button(btn_frame, command=self._run_decompose)
        self.compute_btn.pack(side=tk.RIGHT)

        self.status_label = tk.Label(frame, anchor="w", justify=tk.LEFT)
        self.status_label.pack(fill=tk.X)

    def _apply_language(self) -> None:
        self.root.title(self.tr("title"))
        assert self.materials_label and self.cache_check and self.pick_btn and self.settings_btn and self.compute_btn and self.status_label
        self.materials_label.configure(text=self.tr("materials_label"))
        self.cache_check.configure(text=self.tr("use_cache"))
        self.pick_btn.configure(text=self.tr("pick_product"))
        self.settings_btn.configure(text=self.tr("settings"))
        self.compute_btn.configure(text=self.tr("compute"))
        if self.product_name:
            self.status_label.configure(
                text=f"{self.tr('selected')}: {self.product_name}\n{self.tr('demand')}: {self.required_quantity}\n{self.tr('ready')}"
            )

    def _show_product_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(self.tr("product_dialog_title"))
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("520x220")

        tk.Label(dialog, text=self.tr("product_name")).pack(anchor="w", padx=12, pady=(12, 4))
        product_var = tk.StringVar(value=self.product_name)
        product_combo = ttk.Combobox(dialog, textvariable=product_var, values=self.products)
        product_combo.pack(fill=tk.X, padx=12)

        tk.Label(dialog, text=self.tr("suggestions")).pack(anchor="w", padx=12, pady=(8, 4))
        tk.Label(dialog, text="type text and open dropdown", fg="#666").pack(anchor="w", padx=12)

        tk.Label(dialog, text=self.tr("quantity")).pack(anchor="w", padx=12, pady=(8, 4))
        qty_var = tk.StringVar(value=str(self.required_quantity))
        qty_entry = tk.Entry(dialog, textvariable=qty_var)
        qty_entry.pack(fill=tk.X, padx=12)

        def update_dropdown(*_: object) -> None:
            keyword = product_var.get().strip().lower()
            matches = [p for p in self.products if keyword in p.lower()] if keyword else self.products
            product_combo["values"] = matches[:200]

        def confirm() -> None:
            name = product_var.get().strip()
            if not name:
                messagebox.showerror(self.tr("error"), self.tr("need_product"))
                return
            if name not in self.products:
                messagebox.showerror(self.tr("error"), self.tr("invalid_product"))
                return
            try:
                qty = int(qty_var.get().strip())
            except ValueError:
                messagebox.showerror(self.tr("error"), self.tr("invalid_qty"))
                return
            if qty < 1:
                messagebox.showerror(self.tr("error"), self.tr("invalid_qty"))
                return

            self.product_name = name
            self.required_quantity = qty
            assert self.status_label
            self.status_label.configure(
                text=f"{self.tr('selected')}: {name}\n{self.tr('demand')}: {qty}\n{self.tr('ready')}"
            )
            dialog.destroy()

        product_combo.bind("<KeyRelease>", update_dropdown)
        tk.Button(dialog, text=self.tr("confirm"), command=confirm).pack(fill=tk.X, padx=12, pady=12)
        update_dropdown()

    def _load_cached_inventory(self) -> str:
        if not CACHE_PATH.exists():
            return ""
        try:
            payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            return str(payload.get("inventory_text", ""))
        except Exception:
            return ""

    def _save_cached_inventory(self, inventory_text: str) -> None:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"inventory_text": inventory_text}
        CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _open_settings(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(self.tr("settings_title"))
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("320x140")

        tk.Label(dialog, text=self.tr("language")).pack(anchor="w", padx=12, pady=(12, 4))
        lang_var = tk.StringVar(value=self.language)
        options = [(self.tr("chinese"), "zh"), (self.tr("english"), "en")]
        for text, code in options:
            tk.Radiobutton(dialog, text=text, variable=lang_var, value=code).pack(anchor="w", padx=12)

        def save() -> None:
            self.language = lang_var.get()
            self._apply_language()
            dialog.destroy()

        tk.Button(dialog, text=self.tr("save"), command=save).pack(fill=tk.X, padx=12, pady=12)

    def _show_result_window(self, content: str) -> None:
        result_win = tk.Toplevel(self.root)
        result_win.title(self.tr("result_title"))
        result_win.geometry("700x520")
        result_win.transient(self.root)
        result_win.grab_set()

        frame = tk.Frame(result_win, padx=12, pady=12)
        frame.pack(fill=tk.BOTH, expand=True)

        text = tk.Text(frame, wrap=tk.WORD)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = tk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        text.configure(yscrollcommand=scroll.set)

        text.insert(tk.END, content)
        text.configure(state=tk.DISABLED)

    def _run_decompose(self) -> None:
        if not self.product_name:
            messagebox.showerror(self.tr("error"), self.tr("need_select"))
            return

        assert self.materials_text and self.status_label
        pasted_inventory = self.materials_text.get("1.0", tk.END)
        inventory_text = pasted_inventory
        if self.use_cache_var.get():
            inventory_text = self._load_cached_inventory()
            self.status_label.configure(text=f"{self.status_label.cget('text')}\n{self.tr('cache_notice')}")
        else:
            self._save_cached_inventory(pasted_inventory)

        try:
            result = compute_asteroids(self.product_name, self.required_quantity, inventory_text, self.refinery_file)
        except Exception as exc:
            messagebox.showerror(self.tr("calc_fail"), str(exc))
            return

        lines = [
            f"{self.tr('selected')}: {result['requested_product']}",
            f"{self.tr('demand')}: {result['requested_quantity']}",
            f"{self.tr('runs')}: {result['planned_runs']}",
            f"{self.tr('run_output')}: {result['single_run_output']}",
            f"{self.tr('actual_output')}: {result['actual_output']}",
            "",
            f"{self.tr('asteroid_list')}:",
        ]

        if not result["asteroids"]:
            lines.append(self.tr("none"))
        else:
            for name, qty in result["asteroids"]:
                lines.append(f"- {name}: {qty}")

        self._show_result_window("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 Tkinter 交互式产物分解界面")
    parser.add_argument("--refinery", default="refinery.json", help="Refinery 文件名 默认 refinery.json")
    args = parser.parse_args()

    root = tk.Tk()
    App(root, refinery_file=args.refinery)
    root.mainloop()


if __name__ == "__main__":
    main()
