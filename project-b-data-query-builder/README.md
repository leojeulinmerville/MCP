# Project B: Data Query Builder

FastMCP server (Python) for loading CSV files into an in-memory SQLite database, exploring schema, running safe read-only SQL, and computing column statistics.

## 1) Setup

### Requirements
- Python 3.10+
- `uv` (recommended package/environment manager)

### Install `uv`
- Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

- macOS/Linux (optional):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Create environment and install MCP CLI
From repository root:

```powershell
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install "mcp[cli]"
```

## 2) Run with MCP Inspector

From repository root:

```powershell
cd project-b-data-query-builder
mcp dev server.py
```

In Inspector, test tools with these example inputs:

- `load_csv`
  - `file_path`: `C:\\path\\to\\sample_data.csv`
  - `table_name`: `sales`
- `list_tables`
  - no arguments
- `describe_schema`
  - no arguments
- `run_query`
  - `sql`: `SELECT region, quarter, SUM(revenue) AS total_revenue FROM sales GROUP BY region, quarter ORDER BY total_revenue DESC`
  - `limit`: `50`
- `get_statistics`
  - `table_name`: `sales`
  - `column`: `price`

Resources to inspect:
- `db:/schema`
- `db:/query-history`

## 3) Sample CSV (save manually as `sample_data.csv`)

```csv
quarter,region,product_category,quantity,price,revenue
Q1,North,Electronics,120,199.99,23998.8
Q1,South,Furniture,80,349.50,27960.0
Q1,West,Office Supplies,210,15.25,3202.5
Q2,North,Electronics,95,219.99,20899.05
Q2,South,Furniture,70,329.00,23030.0
Q2,West,Office Supplies,250,14.75,3687.5
Q3,North,Electronics,130,205.00,26650.0
Q3,South,Furniture,90,355.25,31972.5
Q4,North,Electronics,140,210.50,29470.0
Q4,West,Office Supplies,300,13.95,4185.0
```

## 4) Codex CLI Integration via MCP

Official add command format:

```powershell
codex mcp add data-query-builder -- "<ABS_PATH_TO_VENV_PYTHON>" "<ABS_PATH_TO_SERVER_PY>"
```

Windows absolute paths and quoting tips:
- Always wrap paths in double quotes because `C:\\...` may include spaces.
- You can resolve absolute paths in PowerShell:

```powershell
$VENV_PY = (Resolve-Path .\.venv\Scripts\python.exe).Path
$SERVER_PY = (Resolve-Path .\project-b-data-query-builder\server.py).Path
codex mcp add data-query-builder -- "$VENV_PY" "$SERVER_PY"
```

Then open Codex TUI and run:

```text
/mcp
```

Confirm `data-query-builder` is active.

## 5) Multi-Tool Test Scenarios

### Scenario A: Highest revenue region by quarter
- Goal: Load sales data and find the top region per quarter.
- Expected tool call sequence:
  1. `load_csv(file_path, table_name="sales")`
  2. `describe_schema()`
  3. `run_query(sql="WITH ranked AS (SELECT quarter, region, SUM(revenue) AS total_revenue, ROW_NUMBER() OVER (PARTITION BY quarter ORDER BY SUM(revenue) DESC) AS rn FROM sales GROUP BY quarter, region) SELECT quarter, region, total_revenue FROM ranked WHERE rn = 1 ORDER BY quarter", limit=50)`

### Scenario B: Average price per product category
- Goal: Compute average unit price by category.
- Expected tool call sequence:
  1. `list_tables()`
  2. `run_query(sql="SELECT product_category, AVG(price) AS avg_price FROM sales GROUP BY product_category ORDER BY avg_price DESC", limit=50)`

### Scenario C: Statistics for quantity and price
- Goal: Check distribution basics after loading data.
- Expected tool call sequence:
  1. `list_tables()`
  2. `get_statistics(table_name="sales", column="quantity")`
  3. `get_statistics(table_name="sales", column="price")`
  4. `db:/query-history` (resource read to verify logging)

## 6) Comparison Template

### With tools vs without tools

| Dimension | Without tools | With tools |
|---|---|---|
| Accuracy |  |  |
| Specificity |  |  |
| Completeness |  |  |
| Confidence |  |  |
| Latency |  |  |

### Strategy 1 (minimal) vs Strategy 3 (expert)

| Dimension | Strategy 1: Minimal | Strategy 3: Expert workflow |
|---|---|---|
| Schema inspection depth |  |  |
| SQL correctness |  |  |
| Use of statistics |  |  |
| Evidence citation |  |  |
| Reproducibility |  |  |

Ready-to-copy Strategy 3 system prompt:

```text
You are analyzing tabular data through MCP tools. Follow this exact workflow.

Phase 1: Load and inspect schema
1) If data is not loaded, call load_csv.
2) Call list_tables and describe_schema (or db:/schema resource) to map table/column names.
3) Do not assume column names; only use discovered schema.

Phase 2: Query with SQL
1) Write read-only SQL (SELECT/WITH only).
2) Execute with run_query.
3) If query fails, revise SQL using schema evidence and retry.

Phase 3: Compute statistics when needed
1) For columns referenced in conclusions (especially numeric), call get_statistics.
2) Use null counts and mean/min/max to qualify confidence.

Output requirements
- Cite facts by tool source, for example:
  - "From describe_schema: table sales has columns quarter, region, ..."
  - "From run_query: North had highest Q4 revenue ..."
  - "From get_statistics(price): mean=..., nulls=..."
- If evidence is insufficient, say exactly which tool call is needed next.
```

## 7) Notes
- No third-party dependencies are required beyond `mcp[cli]`.
- The server is stateful for one process lifetime because SQLite runs in `:memory:`.
