# Project B: Data Query Builder

## 1 Overview

This project provides a FastMCP server backed by an in-memory SQLite database. It is designed for English-first data analysis workflows where the model:
- loads CSV data,
- inspects available schema,
- executes safe read-only SQL,
- computes column-level statistics,
- and cites tool outputs.

The server currently exposes 5 tools and 2 resources.

## 2 Setup

### Requirements
- Python 3.10+
- `uv`

### Install `uv`
Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Optional macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Create venv and install dependency
From repository root:

```powershell
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install "mcp[cli]"
```

## 3 Run in MCP Inspector

From repository root:

```powershell
cd project-b-data-query-builder
mcp dev server.py
```

If Inspector reports `PORT IS IN USE` for `6277`, stop the existing Inspector/Node process and rerun.

## 4 Codex CLI Integration

Add this server to Codex:

```powershell
codex mcp add data-query-builder -- "<ABS_PATH_TO_VENV_PYTHON>" "<ABS_PATH_TO_SERVER_PY>"
```

Windows absolute-path helper:

```powershell
$VENV_PY = (Resolve-Path .\.venv\Scripts\python.exe).Path
$SERVER_PY = (Resolve-Path .\project-b-data-query-builder\server.py).Path
codex mcp add data-query-builder -- "$VENV_PY" "$SERVER_PY"
```

In Codex TUI:

```text
/mcp
```

Confirm `data-query-builder` is active.

## 5 Tools

### Tool summary

| Tool | Purpose | Typical use order |
|---|---|---|
| `load_csv` | Load CSV into SQLite table with inferred types | First |
| `list_tables` | Show loaded tables and row counts | Early validation |
| `describe_schema` | Show tables and columns/types | Before SQL writing |
| `run_query` | Execute safe read-only SQL with row limits | Core analysis step |
| `get_statistics` | Null/min/max/mean summary for one column | Validation/deep dive |

### 5.1 `load_csv(file_path: str, table_name: str) -> str`

Description: Loads a CSV into a SQLite table with auto-detected column types.

Parameters:

| param | type | required | description |
|---|---|---|---|
| `file_path` | `str` | yes | Path to CSV file |
| `table_name` | `str` | yes | Destination table name |

Return format summary:
- Success JSON keys: `table_name`, `columns` (list of `{name,type}`), `row_count`
- Error JSON key: `error`

Usage example:
- English question: "Load my sales CSV into a table named `sales`."
- Tool invocation inputs:

```json
{
  "file_path": "C:\\data\\sample_data.csv",
  "table_name": "sales"
}
```

- Expected output shape:

```json
{
  "table_name": "sales",
  "columns": [{"name": "quarter", "type": "TEXT"}],
  "row_count": 10
}
```

### 5.2 `list_tables() -> str`

Description: Lists all current user tables with row counts.

Parameters:

| param | type | required | description |
|---|---|---|---|
| _(none)_ | - | - | No inputs |

Return format summary:
- Success JSON keys: `tables` (list of `{table_name,row_count}`)
- Error JSON key: `error`

Usage example:
- English question: "What datasets are loaded right now?"
- Tool invocation inputs:

```json
{}
```

- Expected output shape:

```json
{
  "tables": [
    {"table_name": "sales", "row_count": 10}
  ]
}
```

### 5.3 `describe_schema() -> str`

Description: Returns table/column schema details for all loaded tables.

Parameters:

| param | type | required | description |
|---|---|---|---|
| _(none)_ | - | - | No inputs |

Return format summary:
- Success JSON keys: `tables` where each table includes `table_name` and `columns`
- Each column includes: `name`, `type`, `notnull`, `default`, `pk`
- Error JSON key: `error`

Usage example:
- English question: "Which columns exist in `sales` and what are their types?"
- Tool invocation inputs:

```json
{}
```

- Expected output shape:

```json
{
  "tables": [
    {
      "table_name": "sales",
      "columns": [
        {
          "name": "price",
          "type": "REAL",
          "notnull": false,
          "default": null,
          "pk": false
        }
      ]
    }
  ]
}
```

### 5.4 `run_query(sql: str, limit: int = 50) -> str`

Description: Executes one safe read-only SQL query (`SELECT`/`WITH` only) with result limiting.

Parameters:

| param | type | required | description |
|---|---|---|---|
| `sql` | `str` | yes | SQL query text |
| `limit` | `int` | no | Max rows returned (default 50) |

Return format summary:
- Success JSON keys: `columns`, `rows`, `row_count_returned`, `truncated`
- Error JSON key: `error`

Usage example:
- English question: "Which region had the highest total revenue in Q4?"
- Tool invocation inputs:

```json
{
  "sql": "SELECT region, SUM(revenue) AS total_revenue FROM sales WHERE quarter = 'Q4' GROUP BY region ORDER BY total_revenue DESC",
  "limit": 50
}
```

- Expected output shape:

```json
{
  "columns": ["region", "total_revenue"],
  "rows": [{"region": "North", "total_revenue": 29470.0}],
  "row_count_returned": 1,
  "truncated": false
}
```

### 5.5 `get_statistics(table_name: str, column: str) -> str`

Description: Computes null counts, min/max, and mean (when numeric) for one column.

Parameters:

| param | type | required | description |
|---|---|---|---|
| `table_name` | `str` | yes | Table to analyze |
| `column` | `str` | yes | Column to summarize |

Return format summary:
- Success JSON keys: `table_name`, `column`, `column_type`, `stats`
- `stats` keys: `count_non_null`, `nulls`, `min`, `max`, `mean`
- Error JSON key: `error`

Usage example:
- English question: "What are the distribution basics for `price` in `sales`?"
- Tool invocation inputs:

```json
{
  "table_name": "sales",
  "column": "price"
}
```

- Expected output shape:

```json
{
  "table_name": "sales",
  "column": "price",
  "column_type": "REAL",
  "stats": {
    "count_non_null": 10,
    "nulls": 0,
    "min": 13.95,
    "max": 355.25,
    "mean": 191.343
  }
}
```

## 6 Resources

### `db:/schema`
- Exposes: current schema snapshot, same structure as `describe_schema` output.
- Example read output shape:

```json
{
  "tables": [
    {
      "table_name": "sales",
      "columns": [
        {"name": "quarter", "type": "TEXT", "notnull": false, "default": null, "pk": false}
      ]
    }
  ]
}
```

### `db:/query-history`
- Exposes: all `run_query` attempts in this session.
- Example read output shape:

```json
[
  {
    "timestamp": "2026-03-05T10:20:56.815533+00:00",
    "sql": "SELECT region, SUM(revenue) AS total_revenue FROM sales GROUP BY region",
    "limit": 50,
    "status": "ok",
    "row_count_returned": 3
  },
  {
    "timestamp": "2026-03-05T10:20:57.010000+00:00",
    "sql": "DELETE FROM sales",
    "limit": 50,
    "status": "error",
    "error_message": "Disallowed SQL keyword detected..."
  }
]
```

## 7 Limitations

- Data is process-local and ephemeral (`:memory:` DB). Restarting the server clears all tables/history.
- Type inference in `load_csv` is heuristic and based on CSV string values; mixed-type columns may be inferred as `TEXT`.
- `run_query` rejects any semicolon to avoid multi-statement risks; valid SQL ending with `;` is intentionally blocked.
- SQL safety checks are keyword-based and conservative; some legitimate advanced SQL patterns may be refused.
- Query history is in-memory only and not persisted.

## 8 Testing Scenarios

### Scenario 1: Highest revenue region by quarter
- English question: "After loading sales data, which region is highest-revenue in each quarter?"
- Expected tool sequence: `load_csv` -> `describe_schema` -> `run_query`
- Observed tool sequence (fill after run): `________________________________________`
- SQL used:

```sql
WITH ranked AS (
  SELECT
    quarter,
    region,
    SUM(revenue) AS total_revenue,
    ROW_NUMBER() OVER (PARTITION BY quarter ORDER BY SUM(revenue) DESC) AS rn
  FROM sales
  GROUP BY quarter, region
)
SELECT quarter, region, total_revenue
FROM ranked
WHERE rn = 1
ORDER BY quarter;
```

- Result summary (fill after run): `________________________________________`

### Scenario 2: Average price by product category
- English question: "What is the average price per product category?"
- Expected tool sequence: `list_tables` -> `describe_schema` -> `run_query`
- Observed tool sequence (fill after run): `________________________________________`
- SQL used:

```sql
SELECT product_category, AVG(price) AS avg_price
FROM sales
GROUP BY product_category
ORDER BY avg_price DESC;
```

- Result summary (fill after run): `________________________________________`

### Scenario 3: Quality checks on numeric columns
- English question: "What are nulls/min/max/mean for quantity and price after load?"
- Expected tool sequence: `list_tables` -> `get_statistics(quantity)` -> `get_statistics(price)` -> `db:/query-history`
- Observed tool sequence (fill after run): `________________________________________`
- SQL used: `N/A (statistics tool)`
- Result summary (fill after run): `________________________________________`

## 9 With Tools vs Without Tools

### Complex scenario text
"Given quarterly multi-region sales data with category-level prices and quantities, identify the top region per quarter, compute average price per category, and report confidence qualifiers (nulls/range/mean) for the metrics used in the final recommendation."

### Small data sample for a no-tools run
Paste this into the model prompt when testing without MCP tools:

```csv
quarter,region,product_category,quantity,price,revenue
Q1,North,Electronics,120,199.99,23998.8
Q1,South,Furniture,80,349.50,27960.0
Q2,North,Electronics,95,219.99,20899.05
Q2,South,Furniture,70,329.00,23030.0
Q3,North,Electronics,130,205.00,26650.0
Q4,West,Office Supplies,300,13.95,4185.0
```

### Answer placeholders
- Without tools answer (paste):

```text
[PASTE WITHOUT-TOOLS ANSWER HERE]
```

- With tools answer (paste):

```text
[PASTE WITH-TOOLS ANSWER HERE]
```

### Comparison table (fill after both runs)

| Dimension | Without tools | With tools |
|---|---|---|
| Accuracy |  |  |
| Specificity |  |  |
| Completeness |  |  |
| Confidence |  |  |
| Latency |  |  |

## 10 Prompting Strategy Comparison

### Strategy 1 minimal prompt

```text
Analyze the sales data and answer the user question clearly.
```

### Strategy 3 expert system prompt (project-specific)

```text
You are a data analyst operating through MCP tools for an in-memory SQLite database.

Workflow requirements:
Phase 1: Load and inspect
1) If needed, call load_csv to load the dataset.
2) Call list_tables and describe_schema (or read db:/schema) before writing SQL.
3) Use only discovered table and column names.

Phase 2: Query
1) Write read-only SQL (SELECT/WITH only).
2) Execute via run_query.
3) If a query fails, revise based on schema evidence and rerun.

Phase 3: Statistical validation
1) For key numeric/text columns used in conclusions, call get_statistics.
2) Use nulls/min/max/mean to qualify confidence.

Reporting requirements:
- Cite evidence by tool source, e.g. "From describe_schema...", "From run_query...", "From get_statistics...".
- If uncertain, state exactly which next tool call would resolve uncertainty.
```

### Strategy comparison log (fill during workshop)

| Strategy | Number of tool calls | Planning behavior | Synthesis quality | Errors/repairs |
|---|---|---|---|---|
| Strategy 1 minimal |  |  |  |  |
| Strategy 3 expert |  |  |  |  |

### Observations notes

```text
[Record qualitative observations here: when the model planned, when it guessed, and where tool evidence improved output quality.]
```
