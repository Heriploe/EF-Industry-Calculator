# EF-Industry-Calculator

## 交互式分解界面

使用 Python 自带窗口 Tkinter 运行

```bash
python3 interactive_decompose_app.py
```

交互流程

1. 单窗口界面 顶部直接选择产物和生产数量
2. 下方输入原料库存 可多次粘贴 支持滚轮和 Enter 换行
3. 点击加载缓存库存按钮后 自动用缓存内容替换输入框
4. 点击确认并计算后 打开新的结果窗口 显示 Asteroid 名称及个数

校验规则

- 未选择产物直接点击计算 会弹出警告
- 粘贴库存完全替代基础库存
- 每次计算时 当前输入库存会写入缓存文件 `Inventory/inventory_cache.json`

设置

- 提供语言切换 可在中文与英文间切换
