# EF-Industry-Calculator

## 交互式分解界面

新增 `interactive_decompose_app.py`，用于通过网页交互执行产物分解：

```bash
python3 interactive_decompose_app.py --port 8765
```

打开 `http://localhost:8765` 后：

1. 首先弹出产物输入框，支持根据输入字符联想下拉菜单（来源于 `Product/*.json` 的产物）。
2. 输入所需生产数量并确认。
3. 进入原料输入界面，可多次粘贴内容；文本框支持滚轮查看详细内容，按 Enter 可换行。
4. 点击确认后执行分解逻辑，输出 Asteroid 名称及所需个数。
