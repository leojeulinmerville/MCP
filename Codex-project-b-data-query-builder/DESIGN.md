# Project B Design: Data Query Builder

## 1) Tool Inventory

### `load_csv(file_path: str, table_name: str) -> str`
- One-line description: Load a CSV file into a new SQLite table with auto-detected column types.
- Parameters:
  - `file_path` (`str`): Absolute or relative path to a CSV file.
  - `table_name` (`str`): Target table name to create/populate.
- Return format (exact JSON string):
  - Success:
    - `table_name` (`str`)
    - `columns` (`list[object]`) where each item has:
      - `name` (`str`)
      - `type` (`str`)
    - `row_count` (`int`)
  - Error:
    - `error` (`str`)

### `list_tables() -> str`
- One-line description: List all user tables currently in the in-memory SQLite database.
- Parameters: none
- Return format (exact JSON string):
  - Success:
    - `tables` (`list[object]`) where each item has:
      - `table_name` (`str`)
      - `row_count` (`int`)
  - Error:
    - `error` (`str`)

### `describe_schema() -> str`
- One-line description: Describe every table and each column name/type in the current database.
- Parameters: none
- Return format (exact JSON string):
  - Success:
    - `tables` (`list[object]`) where each item has:
      - `table_name` (`str`)
      - `columns` (`list[object]`) where each item has:
        - `name` (`str`)
        - `type` (`str`)
        - `notnull` (`bool`)
        - `default` (`str | null`)
        - `pk` (`bool`)
  - Error:
    - `error` (`str`)

### `run_query(sql: str, limit: int = 50) -> str`
- One-line description: Execute one read-only SELECT/WITH query with safety checks and bounded results.
- Parameters:
  - `sql` (`str`): SQL query text.
  - `limit` (`int`, default `50`): Maximum number of rows to return.
- Return format (exact JSON string):
  - Success:
    - `columns` (`list[str]`)
    - `rows` (`list[object]`)
    - `row_count_returned` (`int`)
    - `truncated` (`bool`)
  - Error:
    - `error` (`str`)

### `get_statistics(table_name: str, column: str) -> str`
- One-line description: Compute null counts and aggregate stats for one column.
- Parameters:
  - `table_name` (`str`): Existing table name.
  - `column` (`str`): Existing column name.
- Return format (exact JSON string):
  - Success:
    - `table_name` (`str`)
    - `column` (`str`)
    - `column_type` (`str`)
    - `stats` (`object`) with:
      - `count_non_null` (`int`)
      - `nulls` (`int`)
      - `min` (`number | string | null`)
      - `max` (`number | string | null`)
      - `mean` (`number | null`)
  - Error:
    - `error` (`str`)

## 2) Resource Inventory

### `db:/schema`
- Exposes the current schema snapshot for all tables.
- JSON payload is identical to `describe_schema()` success output.

### `db:/query-history`
- Exposes all executed `run_query` attempts in this server session.
- JSON payload: `list[object]` where each item has:
  - `timestamp` (`str`, ISO-8601 UTC)
  - `sql` (`str`)
  - `limit` (`int`)
  - `status` (`"ok" | "error"`)
  - `row_count_returned` (`int`, when `status="ok"`)
  - `error_message` (`str`, when `status="error"`)

## 3) Data Model

In-memory runtime state in `server.py`:
- `conn: sqlite3.Connection`
  - Created once at startup via `create_db()`.
  - Holds all loaded tables in SQLite `:memory:`.
- `query_history: list[dict]`
  - Appended by every `run_query` call.
  - Stores timestamp, sql, limit, status, and either row count or error message.

No other global state is required.

## 4) Division of Labor (3 Parallel Roles)

1. Data Layer Engineer
- Implements CSV ingestion, identifier validation, quoting, and schema/table helpers.

2. Query Safety Engineer
- Implements SQL guardrails (`SELECT/WITH` only, blocked keywords, no semicolons, result limiting) and query history logging.

3. MCP Interface Engineer
- Implements FastMCP tool/resource registration, JSON response contract, README usage/testing flow, and inspector validation.

## 5) Error Cases

- Missing file:
  - `load_csv` returns `{"error": "CSV file not found: ..."}`.
- Empty CSV:
  - `load_csv` returns `{"error": "CSV file is empty: ..."}`.
- Invalid table:
  - `list_tables`/`describe_schema`/`get_statistics`/`run_query` return `{"error": "Table not found: ..."}` or SQLite-derived message.
- Invalid column:
  - `get_statistics` returns `{"error": "Column not found: ..."}`.
- Invalid SQL syntax:
  - `run_query` returns SQLite error + hint to inspect `describe_schema`.
- Disallowed SQL:
  - `run_query` returns `{"error": "Only single SELECT/WITH queries are allowed; mutation keywords are blocked."}`.
- SQLite runtime errors:
  - Any tool catches `sqlite3.Error` and returns readable JSON error messages without crashing the server.

## 6) Test Scenarios and Measurement Plan

The workshop evaluation uses three scenarios aligned with the README:

1. Highest revenue region by quarter
- Expected sequence: `load_csv` -> `describe_schema` -> `run_query`
- Record: observed tool sequence, SQL executed, result summary.

2. Average price by product category
- Expected sequence: `list_tables` -> `describe_schema` -> `run_query`
- Record: observed tool sequence, SQL executed, result summary.

3. Column quality checks (quantity and price)
- Expected sequence: `list_tables` -> `get_statistics(quantity)` -> `get_statistics(price)` -> `db:/query-history`
- Record: observed tool sequence and result summary.

Measurement artifacts to capture:
- With tools vs without tools: accuracy, specificity, completeness, confidence, latency.
- Prompting strategy comparison (Strategy 1 minimal vs Strategy 3 expert):
  - number of tool calls,
  - planning behavior,
  - synthesis quality,
  - errors and repair behavior.
