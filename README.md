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

### Visualization extras

Install plotting support:

```powershell
uv pip install matplotlib
```

If `matplotlib` is not installed, visualization tools return a JSON error with this install hint.

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

Description: Loads a CSV into a SQLite table with auto-detected column types. Relative paths are resolved from the server working directory.

Parameters:

| param | type | required | description |
|---|---|---|---|
| `file_path` | `str` | yes | Path to CSV file |
| `table_name` | `str` | yes | Destination table name |

Return format summary:
- Success JSON keys: `table_name`, `columns` (list of `{name,type}`), `row_count`, `encoding_used`, `replacement_characters_possible`
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
  "row_count": 10,
  "encoding_used": "utf-8-sig",
  "replacement_characters_possible": false
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
- CSV decoding in `load_csv` uses fallback order: `utf-8-sig` -> `utf-8` -> `cp1252` -> `latin-1`.
- If all preferred decoders fail, loading falls back to `utf-8` with `errors="replace"`; text fields may contain replacement characters.
- `run_query` rejects any semicolon to avoid multi-statement risks; valid SQL ending with `;` is intentionally blocked.
- SQL safety checks are keyword-based and conservative; some legitimate advanced SQL patterns may be refused.
- Query history is in-memory only and not persisted.

## 8 Testing Scenarios

### Scenario 1: Highest revenue movie by decade
- English question: "After loading movies data, which movie has the highest revenue in each decade (vote_count >= 1000)?"
- Expected tool sequence: `load_csv` -> `describe_schema` -> `run_query` -> `db:/query-history`
- Observed tool sequence: `load_csv` -> `describe_schema` -> `run_query` -> `db:/query-history`
- SQL used:

```sql
WITH base AS (
  SELECT
    title,
    CAST(strftime('%Y', release_date) AS INTEGER) AS year,
    revenue,
    vote_count
  FROM movies
  WHERE release_date IS NOT NULL
    AND release_date != ''
    AND strftime('%Y', release_date) IS NOT NULL
    AND revenue IS NOT NULL
    AND vote_count IS NOT NULL
    AND vote_count >= 1000
),
ranked AS (
  SELECT
    (CAST(year / 10 AS INTEGER) * 10) AS decade,
    title,
    revenue,
    vote_count,
    ROW_NUMBER() OVER (
      PARTITION BY (CAST(year / 10 AS INTEGER) * 10)
      ORDER BY revenue DESC, vote_count DESC
    ) AS rn
  FROM base
)
SELECT decade, title, revenue, vote_count
FROM ranked
WHERE rn = 1
ORDER BY decade
```

- Result summary: Decade winners (1930s to 2010s) were: Snow White and the Seven Dwarfs, Bambi, Alice in Wonderland, One Hundred and One Dalmatians, Star Wars, E.T. the Extra-Terrestrial, Titanic, Avatar, and Star Wars: The Force Awakens. The highest among these was Avatar (2000s) with revenue 2,787,965,087.

### Scenario 2: Average rating by decade
- English question: "Among movies with vote_count >= 1000, what is the average vote_average by decade?"
- Expected tool sequence: `list_tables` -> `describe_schema` -> `run_query`
- Observed tool sequence: `list_tables` -> `describe_schema` -> `run_query`
- SQL used:

```sql
WITH base AS (
  SELECT
    CAST(strftime('%Y', release_date) AS INTEGER) AS year,
    vote_average,
    vote_count
  FROM movies
  WHERE release_date IS NOT NULL
    AND release_date != ''
    AND strftime('%Y', release_date) IS NOT NULL
    AND vote_average IS NOT NULL
    AND vote_count IS NOT NULL
    AND vote_count >= 1000
)
SELECT
  (CAST(year / 10 AS INTEGER) * 10) AS decade,
  ROUND(AVG(vote_average), 3) AS avg_vote_average,
  COUNT(*) AS movie_count
FROM base
GROUP BY decade
ORDER BY avg_vote_average DESC
```

- Result summary: The highest-decade averages were 1960s (7.650), 1970s (7.638), and 1980s (7.439); the 2010s average was 6.561 across 527 movies. All returned rows fit within the limit (9 decades total).

### Scenario 3: Quality checks on numeric columns
- English question: "What are nulls/min/max/mean for revenue and vote_average after load?"
- Expected tool sequence: `list_tables` -> `get_statistics(revenue)` -> `get_statistics(vote_average)` -> `db:/query-history`
- Observed tool sequence: `list_tables` -> `get_statistics(revenue)` -> `get_statistics(vote_average)` -> `db:/query-history`
- SQL used: `N/A (statistics tool)`
- Result summary: `revenue` stats were count_non_null=45460, nulls=6, min=0, max=2787965087, mean=11209348.5393; `vote_average` stats were count_non_null=45460, nulls=6, min=0.0, max=10.0, mean=5.6182. Reading `db:/query-history` after these calls confirmed the latest logged SQL remained the prior `run_query` entry because `get_statistics` does not append query history.

## 9 With Tools vs Without Tools

### Question used in both runs
"Top 5 movies by revenue among movies with vote_count >= 1000."

### Small data sample for a no-tools run
Paste this into the model prompt when testing without MCP tools:

```csv
title,revenue,vote_count
Avatar,2787965087,12114
Star Wars: The Force Awakens,2068223624,7993
Titanic,1845034188,7770
The Avengers,1519557910,12000
Jurassic World,1513528810,8842
Furious 7,1506249360,4176
Minions,1156730962,4729
Paranormal Activity 3,207039844,848
```

### Answers
- Without tools answer:

```text
From the pasted sample (filtering vote_count >= 1000), the top 5 by revenue are: Avatar (2787965087), Star Wars: The Force Awakens (2068223624), Titanic (1845034188), The Avengers (1519557910), and Jurassic World (1513528810). Paranormal Activity 3 is excluded because vote_count is 848.
```

- With tools answer:

```text
From load_csv + run_query on full movies.csv (45466 rows), the top 5 movies by revenue with vote_count >= 1000 are: Avatar (2787965087), Star Wars: The Force Awakens (2068223624), Titanic (1845034188), The Avengers (1519557910), and Jurassic World (1513528810).
```

### Comparison table

| Dimension | Without tools | With tools |
|---|---|---|
| Accuracy | Correct for pasted sample only | Correct on full dataset with tool-verified SQL output |
| Specificity | Limited to 8 provided rows | Exact top 5 over 45466 rows with explicit filter |
| Completeness | Cannot generalize beyond sample | Full-data answer with row-count-backed scope |
| Confidence | Medium (manual sorting) | High (database execution + typed schema) |
| Latency | Very low | Low (extra tool-call overhead) |

## 10 Prompting Strategy Comparison

### Strategy 1 minimal prompt

```text
Analyze the movies data and answer the user question clearly.
```

### Strategy 3 expert system prompt (project-specific)

```text
You are a data analyst operating through MCP tools for an in-memory SQLite database.

Resources available:
- db:/schema
- db:/query-history

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

### System prompt in code: read prompt:/system

In Codex TUI, call `read_mcp_resource` with this JSON payload:

```json
{"server":"data-query-builder","uri":"prompt:/system"}
```

Question used for both strategies: "Top 5 movies by revenue among movies with vote_count >= 1000."

### Strategy comparison log

| Strategy | Number of tool calls | Planning behavior | Synthesis quality | Errors/repairs |
|---|---|---|---|---|
| Strategy 1 minimal | 3 (`load_csv`, `run_query`, `run_query`) | No explicit planning; queried immediately | Good after repair, but initial column guess was wrong | `no such column: movie_title`, then repaired to `title` |
| Strategy 3 expert | 3 (`load_csv`, `describe_schema`, `run_query`) | Explicit schema reconnaissance before SQL | High on first pass; schema-grounded query | None |

### Observations notes

```text
When schema was skipped (Strategy 1), the first query guessed movie_title and failed; one repair was needed before producing the same top-5 result. With schema-first behavior (Strategy 3), the correct title/revenue/vote_count columns were confirmed up front and the first query succeeded directly.
```
