# EF-Industry-Calculator

## 交互式分解界面（Tkinter）

使用 Python 自带窗口（Tkinter）运行，不使用 HTML：

```bash
python3 interactive_decompose_app.py
```

交互流程：

1. 启动后先弹出产物输入窗口：
   - 输入字符可联想下拉列表（来源于 `Product/*.json` 产物）。
   - 输入所需生产数量并确认。
2. 进入原料输入主窗口：
   - 可多次粘贴库存。
   - 文本框支持滚轮查看详细内容，按 Enter 可换行。
3. 点击“确认并计算”后执行分解，输出 Asteroid 名称及个数。

库存规则：

- 粘贴库存**完全替代**基础库存文件（不会再叠加 `Inventory/inventory.csv`）。
- 粘贴格式支持：`名称\t数量` 或 `名称,数量`（每行一条）。
