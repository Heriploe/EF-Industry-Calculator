#!/usr/bin/env python3
"""Tkinter 交互式分解界面：产物联想 + 数量输入 + 原料粘贴，输出 Asteroid 名称和数量。"""

from __future__ import annotations

import argparse
import math
import tkinter as tk
from tkinter import messagebox
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
    """解析粘贴库存。每行格式：名称\t数量 或 名称,数量。"""
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


def compute_asteroids(product_name: str, required_quantity: int, pasted_inventory_text: str, refinery_file: str) -> dict[str, Any]:
    name_map, category_map = load_types_maps()

    # 用户要求：粘贴库存完全替代基础库存
    inventory = parse_inventory_text(pasted_inventory_text, name_map)

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

        self.product_name = ""
        self.required_quantity = 1

        self.root.title("Industry Decompose (Tkinter)")
        self.root.geometry("760x560")

        self._build_main_window()
        self._show_product_dialog()

    def _build_main_window(self) -> None:
        frame = tk.Frame(self.root, padx=12, pady=12)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="原料输入（可多次粘贴；支持滚轮滚动；Enter 可换行）").pack(anchor="w")

        text_wrapper = tk.Frame(frame)
        text_wrapper.pack(fill=tk.BOTH, expand=True, pady=(8, 8))

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

        tk.Button(btn_frame, text="重新选择产物", command=self._show_product_dialog).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="确认并计算", command=self._run_decompose).pack(side=tk.RIGHT)

        self.result_text = tk.Text(frame, height=12, wrap=tk.WORD)
        self.result_text.pack(fill=tk.BOTH, expand=False)
        self.result_text.configure(state=tk.DISABLED)

    def _show_product_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("输入产物与所需数量")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("480x420")

        tk.Label(dialog, text="输入产物名称（支持字符联想）").pack(anchor="w", padx=12, pady=(12, 4))
        product_entry = tk.Entry(dialog)
        product_entry.pack(fill=tk.X, padx=12)
        product_entry.insert(0, self.product_name)

        tk.Label(dialog, text="联想结果：").pack(anchor="w", padx=12, pady=(10, 4))
        suggestion_list = tk.Listbox(dialog, height=12)
        suggestion_list.pack(fill=tk.BOTH, expand=True, padx=12)

        tk.Label(dialog, text="所需生产数量：").pack(anchor="w", padx=12, pady=(10, 4))
        quantity_var = tk.StringVar(value=str(self.required_quantity))
        quantity_entry = tk.Entry(dialog, textvariable=quantity_var)
        quantity_entry.pack(fill=tk.X, padx=12)

        def refresh_suggestions(*_: object) -> None:
            keyword = product_entry.get().strip().lower()
            suggestion_list.delete(0, tk.END)
            matches = [p for p in self.products if keyword in p.lower()] if keyword else self.products[:]
            for name in matches[:200]:
                suggestion_list.insert(tk.END, name)

        def select_current(_: object | None = None) -> None:
            selection = suggestion_list.curselection()
            if not selection:
                return
            selected_name = suggestion_list.get(selection[0])
            product_entry.delete(0, tk.END)
            product_entry.insert(0, selected_name)

        def confirm() -> None:
            name = product_entry.get().strip()
            if not name:
                messagebox.showerror("错误", "请先输入产物名称")
                return
            if name not in self.products:
                messagebox.showerror("错误", "产物不存在，请从联想列表选择或检查拼写")
                return

            try:
                qty = int(quantity_var.get().strip())
            except ValueError:
                messagebox.showerror("错误", "数量必须是正整数")
                return
            if qty < 1:
                messagebox.showerror("错误", "数量必须 >= 1")
                return

            self.product_name = name
            self.required_quantity = qty
            self._set_result(f"已选择产物: {name}\n需求数量: {qty}\n请粘贴库存后点击“确认并计算”。")
            dialog.destroy()

        product_entry.bind("<KeyRelease>", refresh_suggestions)
        suggestion_list.bind("<Double-Button-1>", select_current)
        suggestion_list.bind("<<ListboxSelect>>", select_current)

        tk.Button(dialog, text="确认", command=confirm).pack(padx=12, pady=12, fill=tk.X)
        refresh_suggestions()

    def _set_result(self, content: str) -> None:
        self.result_text.configure(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, content)
        self.result_text.configure(state=tk.DISABLED)

    def _run_decompose(self) -> None:
        if not self.product_name:
            messagebox.showerror("错误", "请先选择产物和数量")
            return

        pasted_inventory = self.materials_text.get("1.0", tk.END)
        try:
            result = compute_asteroids(
                product_name=self.product_name,
                required_quantity=self.required_quantity,
                pasted_inventory_text=pasted_inventory,
                refinery_file=self.refinery_file,
            )
        except Exception as exc:
            messagebox.showerror("计算失败", str(exc))
            return

        lines = [
            f"产物: {result['requested_product']}",
            f"需求数量: {result['requested_quantity']}",
            f"执行次数: {result['planned_runs']} (单次产出 {result['single_run_output']}，实际产出 {result['actual_output']})",
            "",
            "Asteroid 名称及个数:",
        ]

        if not result["asteroids"]:
            lines.append("(无)")
        else:
            for name, qty in result["asteroids"]:
                lines.append(f"- {name}: {qty}")

        self._set_result("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 Tkinter 交互式产物分解界面")
    parser.add_argument("--refinery", default="refinery.json", help="Refinery 文件名，默认 refinery.json")
    args = parser.parse_args()

    root = tk.Tk()
    App(root, refinery_file=args.refinery)
    root.mainloop()


if __name__ == "__main__":
    main()
