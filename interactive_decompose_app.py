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
SETTINGS_PATH = Path(__file__).resolve().parent / "Inventory" / "app_settings.json"
REFINERY_OPTIONS = ["refinery.json", "heavy_refinery.json", "field_refinery.json"]

I18N: dict[str, dict[str, str]] = {
    "zh": {
        "title": "产物分解工具",
        "materials_label": "原料输入 可多次粘贴 支持滚轮和换行",
        "load_cache": "加载缓存库存",
        "settings": "设置",
        "compute": "确认并计算",
        "product_name": "产物名称",
        "quantity": "生产数量",
        "refinery": "Refinery",
        "error": "错误",
        "calc_fail": "计算失败",
        "need_product": "请先选择产物",
        "invalid_product": "产物不存在",
        "invalid_qty": "数量必须是正整数",
        "invalid_refinery": "Refinery 选项无效",
        "selected": "已选择产物",
        "demand": "需求数量",
        "selected_refinery": "当前 Refinery",
        "ready": "请粘贴库存后点击确认并计算",
        "result_title": "分解结果",
        "runs": "执行次数",
        "run_output": "单次产出",
        "actual_output": "实际产出",
        "asteroid_list": "Asteroid 名称及个数",
        "skipped_list": "未分解原料",
        "field_hint": "若未分解原料较多 可能是 field_refinery 配方覆盖不足",
        "none": "无",
        "settings_title": "设置",
        "language": "语言",
        "chinese": "中文",
        "english": "English",
        "save": "保存",
        "cache_loaded": "已加载缓存库存",
        "cache_empty": "缓存库存为空",
    },
    "en": {
        "title": "Product Decompose Tool",
        "materials_label": "Material input paste multiple times scroll and newline supported",
        "load_cache": "Load cached inventory",
        "settings": "Settings",
        "compute": "Confirm and run",
        "product_name": "Product name",
        "quantity": "Quantity",
        "refinery": "Refinery",
        "error": "Error",
        "calc_fail": "Calculation failed",
        "need_product": "Please select a product",
        "invalid_product": "Product not found",
        "invalid_qty": "Quantity must be positive integer",
        "invalid_refinery": "Invalid refinery option",
        "selected": "Selected product",
        "demand": "Required quantity",
        "selected_refinery": "Selected refinery",
        "ready": "Paste inventory then confirm and run",
        "result_title": "Decompose result",
        "runs": "Runs",
        "run_output": "Output per run",
        "actual_output": "Actual output",
        "asteroid_list": "Asteroid name and count",
        "skipped_list": "Undecomposed materials",
        "field_hint": "Many undecomposed materials can mean field_refinery has limited recipe coverage",
        "none": "None",
        "settings_title": "Settings",
        "language": "Language",
        "chinese": "中文",
        "english": "English",
        "save": "Save",
        "cache_loaded": "Cached inventory loaded",
        "cache_empty": "Cached inventory is empty",
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
    producible = {out_type for recipe in recipes for out_type, _ in recipe.outputs}
    end_state, _ = solve_integer_program(initial_state, inventory, recipes, category_map, overproduce_buffer=1)

    asteroids = [
        (name_map.get(type_id, ""), quantity)
        for type_id, quantity in end_state.items()
        if quantity > 0 and category_map.get(type_id, "") == "Asteroid"
    ]
    asteroids.sort(key=lambda row: row[0])

    skipped = [
        (name_map.get(type_id, ""), quantity)
        for type_id, quantity in end_state.items()
        if quantity > 0 and category_map.get(type_id, "") != "Asteroid" and type_id not in producible
    ]
    skipped.sort(key=lambda row: row[0])

    return {
        "requested_product": product_name,
        "requested_quantity": required_quantity,
        "planned_runs": runs,
        "single_run_output": output_qty,
        "actual_output": runs * output_qty,
        "asteroids": asteroids,
        "skipped": skipped,
    }


class App:
    def __init__(self, root: tk.Tk, refinery_file: str):
        self.root = root
        self.name_map, self.category_map = load_types_maps()
        self.products = collect_product_names(self.name_map, self.category_map)

        self.language = self._load_language_setting()
        default_refinery = refinery_file if refinery_file in REFINERY_OPTIONS else REFINERY_OPTIONS[0]

        self.product_var = tk.StringVar()
        self.quantity_var = tk.StringVar(value="1")
        self.refinery_var = tk.StringVar(value=default_refinery)

        self.product_label: tk.Label | None = None
        self.quantity_label: tk.Label | None = None
        self.refinery_label: tk.Label | None = None
        self.product_combo: ttk.Combobox | None = None
        self.refinery_combo: ttk.Combobox | None = None
        self.materials_label: tk.Label | None = None
        self.load_cache_btn: tk.Button | None = None
        self.settings_btn: tk.Button | None = None
        self.compute_btn: tk.Button | None = None
        self.status_label: tk.Label | None = None
        self.materials_text: tk.Text | None = None

        self.result_window: tk.Toplevel | None = None
        self.result_text: tk.Text | None = None

        self.root.geometry("820x580")
        self._build_main_window()
        self._apply_language()

    def tr(self, key: str) -> str:
        return I18N[self.language][key]

    def _load_language_setting(self) -> str:
        if not SETTINGS_PATH.exists():
            return "en"
        try:
            payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            language = str(payload.get("language", "en"))
            return language if language in I18N else "en"
        except Exception:
            return "en"

    def _save_language_setting(self) -> None:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps({"language": self.language}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _build_main_window(self) -> None:
        frame = tk.Frame(self.root, padx=12, pady=12)
        frame.pack(fill=tk.BOTH, expand=True)

        top = tk.Frame(frame)
        top.pack(fill=tk.X, pady=(0, 8))

        self.product_label = tk.Label(top)
        self.product_label.grid(row=0, column=0, sticky="w")
        self.product_combo = ttk.Combobox(top, textvariable=self.product_var, values=self.products)
        self.product_combo.grid(row=0, column=1, sticky="ew", padx=(8, 12))

        self.quantity_label = tk.Label(top)
        self.quantity_label.grid(row=0, column=2, sticky="w")
        qty_entry = tk.Entry(top, textvariable=self.quantity_var, width=8)
        qty_entry.grid(row=0, column=3, sticky="w", padx=(8, 12))

        self.refinery_label = tk.Label(top)
        self.refinery_label.grid(row=0, column=4, sticky="w")
        self.refinery_combo = ttk.Combobox(top, textvariable=self.refinery_var, values=REFINERY_OPTIONS, state="readonly", width=18)
        self.refinery_combo.grid(row=0, column=5, sticky="w", padx=(8, 0))

        top.columnconfigure(1, weight=1)

        self.product_combo.bind("<KeyRelease>", self._update_dropdown)

        self.materials_label = tk.Label(frame)
        self.materials_label.pack(anchor="w")

        text_wrapper = tk.Frame(frame)
        text_wrapper.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

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

        self.load_cache_btn = tk.Button(btn_frame, command=self._load_cache_into_input)
        self.load_cache_btn.pack(side=tk.LEFT)

        self.settings_btn = tk.Button(btn_frame, command=self._open_settings)
        self.settings_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.compute_btn = tk.Button(btn_frame, command=self._run_decompose)
        self.compute_btn.pack(side=tk.RIGHT)

        self.status_label = tk.Label(frame, anchor="w", justify=tk.LEFT)
        self.status_label.pack(fill=tk.X)

    def _apply_language(self) -> None:
        self.root.title(self.tr("title"))
        assert self.product_label and self.quantity_label and self.refinery_label and self.materials_label
        assert self.load_cache_btn and self.settings_btn and self.compute_btn and self.status_label

        self.product_label.configure(text=self.tr("product_name"))
        self.quantity_label.configure(text=self.tr("quantity"))
        self.refinery_label.configure(text=self.tr("refinery"))
        self.materials_label.configure(text=self.tr("materials_label"))
        self.load_cache_btn.configure(text=self.tr("load_cache"))
        self.settings_btn.configure(text=self.tr("settings"))
        self.compute_btn.configure(text=self.tr("compute"))
        self._refresh_status()

    def _refresh_status(self, extra: str = "") -> None:
        assert self.status_label
        product_name = self.product_var.get().strip()
        qty_text = self.quantity_var.get().strip() or "1"
        refinery = self.refinery_var.get().strip() or REFINERY_OPTIONS[0]
        lines = []
        if product_name:
            lines.append(f"{self.tr('selected')}: {product_name}")
        lines.append(f"{self.tr('demand')}: {qty_text}")
        lines.append(f"{self.tr('selected_refinery')}: {refinery}")
        lines.append(self.tr("ready"))
        if extra:
            lines.append(extra)
        self.status_label.configure(text="\n".join(lines))

    def _update_dropdown(self, *_: object) -> None:
        assert self.product_combo
        keyword = self.product_var.get().strip().lower()
        matches = [p for p in self.products if keyword in p.lower()] if keyword else self.products
        self.product_combo["values"] = matches[:200]

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
        CACHE_PATH.write_text(json.dumps({"inventory_text": inventory_text}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_cache_into_input(self) -> None:
        assert self.materials_text
        cached = self._load_cached_inventory()
        if not cached:
            messagebox.showwarning(self.tr("error"), self.tr("cache_empty"))
            return
        self.materials_text.delete("1.0", tk.END)
        self.materials_text.insert(tk.END, cached)
        self._refresh_status(self.tr("cache_loaded"))

    def _open_settings(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(self.tr("settings_title"))
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("320x140")

        tk.Label(dialog, text=self.tr("language")).pack(anchor="w", padx=12, pady=(12, 4))
        lang_var = tk.StringVar(value=self.language)
        for text, code in [(self.tr("chinese"), "zh"), (self.tr("english"), "en")]:
            tk.Radiobutton(dialog, text=text, variable=lang_var, value=code).pack(anchor="w", padx=12)

        def save() -> None:
            self.language = lang_var.get()
            self._save_language_setting()
            self._apply_language()
            dialog.destroy()

        tk.Button(dialog, text=self.tr("save"), command=save).pack(fill=tk.X, padx=12, pady=12)

    def _show_result_window(self, content: str) -> None:
        if self.result_window and self.result_window.winfo_exists() and self.result_text:
            self.result_text.configure(state=tk.NORMAL)
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, content)
            self.result_text.configure(state=tk.DISABLED)
            self.result_window.lift()
            self.result_window.focus_force()
            return

        self.result_window = tk.Toplevel(self.root)
        self.result_window.title(self.tr("result_title"))
        self.result_window.geometry("700x520")

        frame = tk.Frame(self.result_window, padx=12, pady=12)
        frame.pack(fill=tk.BOTH, expand=True)

        self.result_text = tk.Text(frame, wrap=tk.WORD)
        self.result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = tk.Scrollbar(frame, orient=tk.VERTICAL, command=self.result_text.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.result_text.configure(yscrollcommand=scroll.set)

        self.result_text.insert(tk.END, content)
        self.result_text.configure(state=tk.DISABLED)

    def _run_decompose(self) -> None:
        assert self.materials_text

        product_name = self.product_var.get().strip()
        if not product_name:
            messagebox.showwarning(self.tr("error"), self.tr("need_product"))
            return
        if product_name not in self.products:
            messagebox.showerror(self.tr("error"), self.tr("invalid_product"))
            return

        refinery = self.refinery_var.get().strip()
        if refinery not in REFINERY_OPTIONS:
            messagebox.showerror(self.tr("error"), self.tr("invalid_refinery"))
            return

        try:
            required_quantity = int(self.quantity_var.get().strip())
        except ValueError:
            messagebox.showerror(self.tr("error"), self.tr("invalid_qty"))
            return
        if required_quantity < 1:
            messagebox.showerror(self.tr("error"), self.tr("invalid_qty"))
            return

        pasted_inventory = self.materials_text.get("1.0", tk.END)
        self._save_cached_inventory(pasted_inventory)

        try:
            result = compute_asteroids(product_name, required_quantity, pasted_inventory, refinery)
        except Exception as exc:
            messagebox.showerror(self.tr("calc_fail"), str(exc))
            return

        self._refresh_status()

        lines = [
            f"{self.tr('selected')}: {result['requested_product']}",
            f"{self.tr('demand')}: {result['requested_quantity']}",
            f"{self.tr('selected_refinery')}: {refinery}",
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

        if result["skipped"]:
            lines.append("")
            lines.append(f"{self.tr('skipped_list')}:")
            for name, qty in result["skipped"]:
                lines.append(f"- {name}: {qty}")
            if refinery == "field_refinery.json":
                lines.append(self.tr("field_hint"))

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
