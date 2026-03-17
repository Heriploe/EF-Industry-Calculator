# EF-Industry-Calculator

## 交互式分解界面

使用 Python 自带窗口 Tkinter 运行

```bash
python3 interactive_decompose_app.py
```

交互流程

1. 单窗口界面 顶部直接选择产物 生产数量 以及 Refinery
2. Refinery 支持三种选项
   - `refinery.json`
   - `heavy_refinery.json`
   - `field_refinery.json`
3. 下方输入原料库存 可多次粘贴 支持滚轮和 Enter 换行
4. 点击加载缓存库存按钮后 自动用缓存内容替换输入框
5. 点击确认并计算后 若结果窗口已打开则刷新原窗口 否则新建窗口

校验规则

- 未选择产物直接点击计算 会弹出警告
- 粘贴库存完全替代基础库存
- 每次计算时 当前输入库存会写入缓存文件 `Inventory/inventory_cache.json`

语言与设置缓存

- 程序默认语言为英文
- 在设置中切换语言后 会保存到 `Inventory/app_settings.json`
- 下次启动会自动恢复上次选择的语言

关于 `field_refinery.json` 无法计算的原因

- 并非界面故障 主要是 `field_refinery.json` 的配方覆盖范围较小
- 某些产物分解时会出现较多未分解原料 因此可能看起来像无法计算
- 结果窗口已增加“未分解原料”展示 并在选择 `field_refinery.json` 时提示该原因


## 打包可执行文件

请在**非管理员终端**运行 PyInstaller（官方已提示管理员运行将被后续版本禁止）。

已提供打包脚本 `build_interactive_decompose_app.sh`，会自动检查并安装 PyInstaller，然后输出可执行文件。

```bash
./build_interactive_decompose_app.sh
```

打包产物位置：

- Linux/macOS: `dist/interactive_decompose_app`
- Windows (在 Windows 环境执行): `dist/interactive_decompose_app.exe`

同时仓库内包含 `interactive_decompose_app.spec`，可直接用 spec 方式打包：

```bash
python3 -m PyInstaller interactive_decompose_app.spec
```

说明：`interactive_decompose_app.spec` 已兼容 PyInstaller 执行环境中 `__file__` 不存在的情况。
