import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from sqlite_helper import create_db, load_csv_to_table

mcp = FastMCP("data-query-builder")
conn = create_db()
query_history: list[dict[str, Any]] = []
BLOCKED_KEYWORDS = re.compile(r"\b(drop|delete|alter|insert|update)\b", re.IGNORECASE)


def _json_error(message: str) -> str:
    return json.dumps({"error": message})


def _validate_identifier(name: str, kind: str) -> str | None:
    if not isinstance(name, str):
        return f"{kind} must be a string."
    if "\x00" in name:
        return f"{kind} must not contain null bytes."
    normalized = name.strip()
    if not normalized:
        return f"{kind} must not be empty."
    return None


def _quote_identifier(identifier: str) -> str:
    return f'"{identifier.replace("\"", "\"\"")}"'


def _current_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_history(
    *,
    sql: str,
    limit: int,
    status: str,
    row_count_returned: int | None = None,
    error_message: str | None = None,
) -> None:
    entry: dict[str, Any] = {
        "timestamp": _current_timestamp(),
        "sql": sql,
        "limit": limit,
        "status": status,
    }
    if status == "ok":
        entry["row_count_returned"] = row_count_returned if row_count_returned is not None else 0
    else:
        entry["error_message"] = error_message or "Unknown error"
    query_history.append(entry)


def _table_exists(table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)
    ).fetchone()
    return row is not None


def _schema_snapshot() -> dict[str, Any]:
    tables: list[dict[str, Any]] = []
    table_rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()

    for table_row in table_rows:
        table_name = table_row["name"]
        pragma_rows = conn.execute(
            f"PRAGMA table_info({_quote_identifier(table_name)})"
        ).fetchall()
        columns = [
            {
                "name": column_row["name"],
                "type": column_row["type"],
                "notnull": bool(column_row["notnull"]),
                "default": column_row["dflt_value"],
                "pk": bool(column_row["pk"]),
            }
            for column_row in pragma_rows
        ]
        tables.append({"table_name": table_name, "columns": columns})

    return {"tables": tables}


def _is_numeric_type(column_type: str) -> bool:
    normalized = (column_type or "").upper()
    return any(token in normalized for token in ["INT", "REAL", "FLOA", "DOUB", "NUM"])


@mcp.tool()
def load_csv(file_path: str, table_name: str) -> str:
    """Load a CSV into a new SQLite table with auto-detected types.

    Use this first when you need to make CSV data queryable in the in-memory DB.
    Returns JSON: {"table_name", "columns"[{"name", "type"}], "row_count"}.
    Common errors: file not found, empty CSV, invalid table name, or SQLite create/insert errors.
    """
    table_error = _validate_identifier(table_name, "table_name")
    if table_error:
        return _json_error(table_error)
    if not isinstance(file_path, str) or not file_path.strip():
        return _json_error("file_path must be a non-empty string.")
    if "\x00" in file_path:
        return _json_error("file_path must not contain null bytes.")

    raw_path = file_path.strip()
    path_obj = Path(raw_path).expanduser()
    absolute_path = (Path.cwd() / path_obj).resolve() if not path_obj.is_absolute() else path_obj.resolve()

    try:
        loaded = load_csv_to_table(conn, str(absolute_path), table_name.strip())
        columns = [{"name": name, "type": col_type} for name, col_type in loaded["columns"]]
        return json.dumps(
            {
                "table_name": loaded["table_name"],
                "columns": columns,
                "row_count": loaded["row_count"],
                "encoding_used": loaded.get("encoding_used"),
                "replacement_characters_possible": loaded.get(
                    "replacement_characters_possible", False
                ),
            }
        )
    except FileNotFoundError:
        return _json_error(f"CSV file not found: {absolute_path}")
    except ValueError as exc:
        return _json_error(str(exc))
    except sqlite3.Error as exc:
        return _json_error(f"SQLite error while loading CSV: {exc}")
    except Exception as exc:  # defensive catch to keep server alive
        return _json_error(f"Unexpected error while loading CSV: {exc}")


@mcp.tool()
def list_tables() -> str:
    """List all current SQLite tables and row counts in the in-memory database.

    Use this to quickly verify which datasets are loaded before writing SQL.
    Returns JSON: {"tables": [{"table_name", "row_count"}] }.
    Common errors: SQLite metadata read issues or count query failures.
    """
    try:
        tables = []
        table_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        for table_row in table_rows:
            table_name = table_row["name"]
            count_row = conn.execute(
                f"SELECT COUNT(*) AS row_count FROM {_quote_identifier(table_name)}"
            ).fetchone()
            tables.append({"table_name": table_name, "row_count": int(count_row["row_count"])})
        return json.dumps({"tables": tables})
    except sqlite3.Error as exc:
        return _json_error(f"SQLite error while listing tables: {exc}")
    except Exception as exc:
        return _json_error(f"Unexpected error while listing tables: {exc}")


@mcp.tool()
def describe_schema() -> str:
    """Describe all tables with column names and SQLite types.

    Use this after loading data or before querying to understand available fields.
    Returns JSON: {"tables": [{"table_name", "columns": [{"name", "type", "notnull", "default", "pk"}]}]}.
    Common errors: malformed schema metadata or SQLite PRAGMA failures.
    """
    try:
        return json.dumps(_schema_snapshot())
    except sqlite3.Error as exc:
        return _json_error(f"SQLite error while describing schema: {exc}")
    except Exception as exc:
        return _json_error(f"Unexpected error while describing schema: {exc}")


@mcp.tool()
def run_query(sql: str, limit: int = 50) -> str:
    """Run one read-only SELECT/WITH SQL query with safety checks.

    Use this to answer analysis questions once schema is known; DML/DDL is blocked.
    Returns JSON: {"columns", "rows", "row_count_returned", "truncated"}.
    Common errors: blocked keywords, semicolons/multiple statements, non-SELECT SQL, syntax errors, or missing tables/columns.
    """
    query_text = sql if isinstance(sql, str) else ""

    if not isinstance(limit, int):
        message = "limit must be an integer."
        _record_history(sql=query_text, limit=50, status="error", error_message=message)
        return _json_error(message)

    if limit <= 0:
        message = "limit must be greater than 0."
        _record_history(sql=query_text, limit=limit, status="error", error_message=message)
        return _json_error(message)

    if not isinstance(sql, str) or not sql.strip():
        message = "sql must be a non-empty string."
        _record_history(sql=query_text, limit=limit, status="error", error_message=message)
        return _json_error(message)

    normalized = sql.strip()
    lowered = normalized.lower()

    if ";" in normalized:
        message = "Semicolons are not allowed. Submit exactly one SELECT/WITH statement without ';'."
        _record_history(sql=normalized, limit=limit, status="error", error_message=message)
        return _json_error(message)

    blocked = BLOCKED_KEYWORDS.search(normalized)
    if blocked:
        message = (
            "Disallowed SQL keyword detected. Only read-only SELECT/WITH queries are allowed; "
            "DROP, DELETE, ALTER, INSERT, and UPDATE are blocked."
        )
        _record_history(sql=normalized, limit=limit, status="error", error_message=message)
        return _json_error(message)

    if not (lowered.startswith("select") or lowered.startswith("with")):
        message = "Only SELECT or WITH queries are allowed."
        _record_history(sql=normalized, limit=limit, status="error", error_message=message)
        return _json_error(message)

    has_limit = re.search(r"\blimit\b", normalized, flags=re.IGNORECASE) is not None
    executable_sql = normalized if has_limit else f"{normalized}\nLIMIT {limit}"

    try:
        cursor = conn.execute(executable_sql)
        columns = [col[0] for col in (cursor.description or [])]
        fetched_rows = cursor.fetchmany(limit + 1)
        truncated = len(fetched_rows) > limit
        safe_rows = fetched_rows[:limit]
        row_dicts = [dict(row) for row in safe_rows]

        payload = {
            "columns": columns,
            "rows": row_dicts,
            "row_count_returned": len(row_dicts),
            "truncated": truncated,
        }
        _record_history(
            sql=normalized,
            limit=limit,
            status="ok",
            row_count_returned=payload["row_count_returned"],
        )
        return json.dumps(payload, default=str)
    except sqlite3.Error as exc:
        message = f"SQLite query error: {exc}. Hint: run describe_schema to verify table and column names."
        _record_history(sql=normalized, limit=limit, status="error", error_message=message)
        return _json_error(message)
    except Exception as exc:
        message = f"Unexpected query error: {exc}"
        _record_history(sql=normalized, limit=limit, status="error", error_message=message)
        return _json_error(message)


@mcp.tool()
def get_statistics(table_name: str, column: str) -> str:
    """Compute summary stats for one column in a table.

    Use this when you need null counts, min/max, and mean for exploratory analysis.
    Returns JSON: {"table_name", "column", "column_type", "stats"{count_non_null, nulls, min, max, mean}}.
    Common errors: missing table/column, invalid identifiers, or SQLite aggregation failures.
    """
    table_error = _validate_identifier(table_name, "table_name")
    if table_error:
        return _json_error(table_error)
    column_error = _validate_identifier(column, "column")
    if column_error:
        return _json_error(column_error)

    normalized_table = table_name.strip()
    normalized_column = column.strip()

    try:
        if not _table_exists(normalized_table):
            return _json_error(f"Table not found: {normalized_table}")

        column_info = conn.execute(
            f"PRAGMA table_info({_quote_identifier(normalized_table)})"
        ).fetchall()
        by_name = {row["name"]: row for row in column_info}
        if normalized_column not in by_name:
            return _json_error(
                f"Column not found: {normalized_column}. Hint: run describe_schema for valid columns."
            )

        column_type = by_name[normalized_column]["type"] or ""
        column_is_numeric = _is_numeric_type(column_type)

        quoted_table = _quote_identifier(normalized_table)
        quoted_column = _quote_identifier(normalized_column)

        if column_is_numeric:
            stats_query = (
                f"SELECT "
                f"COUNT({quoted_column}) AS count_non_null, "
                f"SUM(CASE WHEN {quoted_column} IS NULL THEN 1 ELSE 0 END) AS nulls, "
                f"MIN({quoted_column}) AS min_value, "
                f"MAX({quoted_column}) AS max_value, "
                f"AVG({quoted_column}) AS mean_value "
                f"FROM {quoted_table}"
            )
        else:
            stats_query = (
                f"SELECT "
                f"COUNT({quoted_column}) AS count_non_null, "
                f"SUM(CASE WHEN {quoted_column} IS NULL THEN 1 ELSE 0 END) AS nulls, "
                f"MIN({quoted_column}) AS min_value, "
                f"MAX({quoted_column}) AS max_value, "
                f"NULL AS mean_value "
                f"FROM {quoted_table}"
            )

        row = conn.execute(stats_query).fetchone()
        stats = {
            "count_non_null": int(row["count_non_null"] or 0),
            "nulls": int(row["nulls"] or 0),
            "min": row["min_value"],
            "max": row["max_value"],
            "mean": row["mean_value"] if column_is_numeric else None,
        }

        return json.dumps(
            {
                "table_name": normalized_table,
                "column": normalized_column,
                "column_type": column_type,
                "stats": stats,
            },
            default=str,
        )
    except sqlite3.Error as exc:
        return _json_error(f"SQLite error while computing statistics: {exc}")
    except Exception as exc:
        return _json_error(f"Unexpected error while computing statistics: {exc}")


@mcp.resource("db:/schema")
def schema_resource() -> str:
    try:
        return json.dumps(_schema_snapshot())
    except Exception as exc:
        return _json_error(f"Unable to produce schema resource: {exc}")


@mcp.resource("db:/query-history")
def query_history_resource() -> str:
    try:
        return json.dumps(query_history, default=str)
    except Exception as exc:
        return _json_error(f"Unable to produce query history resource: {exc}")


if __name__ == "__main__":
    mcp.run()
