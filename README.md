# EF-Industry-Calculator

## 导出产物蓝图脚本

新增 `export_blueprints.py`：根据产物名称（支持部分匹配、不区分大小写）从 `industry_blueprints` 数据中筛选蓝图，并导出为 `<产物名>_blueprint.json` 文件；同名多条会自动加序号。

### 用法

```bash
python export_blueprints.py "steel"
```

可选参数：

- `-s/--source`：指定数据源 JSON 文件（默认 `industry_blueprints.json`）
- `-o/--output-dir`：指定导出目录（默认当前目录）
