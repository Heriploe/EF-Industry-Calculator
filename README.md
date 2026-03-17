# EF-Industry-Calculator

## 交互式分解界面

使用 Python 自带窗口 Tkinter 运行

```bash
python3 interactive_decompose_app.py
```

交互流程

1. 启动后先弹出产物输入窗口
   - 输入字符后可在下拉菜单联想产物 来源是 `Product/*.json`
   - 输入所需生产数量并确认
2. 进入原料输入主窗口
   - 可多次粘贴库存
   - 输入框支持滚轮查看详细内容 按 Enter 可换行
   - 可勾选使用缓存库存
3. 点击确认并计算后打开新的结果窗口 显示 Asteroid 名称及个数

库存规则

- 粘贴库存完全替代基础库存
- 不叠加 `Inventory/inventory.csv`
- 每次计算时 当前粘贴库存会写入缓存
- 勾选使用缓存库存时 会直接读取缓存库存

设置

- 提供语言切换 可在中文与英文间切换
