import json
import math
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

from sqlite_helper import create_db, load_csv_to_table

mcp = FastMCP("data-query-builder")
conn = create_db()
query_history: list[dict[str, Any]] = []
plots: dict[str, dict[str, Any]] = {}
PLOTS_DIR = Path(__file__).resolve().parent / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)
MAX_PLOT_ROWS = 50_000
MAX_BAR_TOP_N = 200
DEFAULT_FIGURE_SIZE = (11, 6)
DEFAULT_DPI = 160
BLOCKED_KEYWORDS = re.compile(r"\b(drop|delete|alter|insert|update)\b", re.IGNORECASE)


def _json_error(message: str) -> str:
    return json.dumps({"error": message})


def _dict_error(message: str, hint: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": message}
    if hint:
        payload["hint"] = hint
    return payload


def _validate_identifier(name: str, kind: str) -> str | None:
    if not isinstance(name, str):
        return f"{kind} must be a string."
    if "\x00" in name:
        return f"{kind} must not contain null bytes."
    normalized = name.strip()
    if not normalized:
        return f"{kind} must not be empty."
    return None


def _normalize_identifier(name: str, kind: str) -> tuple[str | None, dict[str, Any] | None]:
    error = _validate_identifier(name, kind)
    if error:
        return None, _dict_error(error)
    return name.strip(), None


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


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


def _get_table_columns(table_name: str) -> dict[str, sqlite3.Row]:
    rows = conn.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()
    return {row["name"]: row for row in rows}


def _validate_table_and_columns(
    table_name: str, columns: list[tuple[str, str]]
) -> tuple[str | None, dict[str, str] | None, dict[str, Any] | None]:
    normalized_table, table_error = _normalize_identifier(table_name, "table_name")
    if table_error:
        return None, None, table_error

    if normalized_table is None:
        return None, None, _dict_error("table_name must be a non-empty string.")

    if not _table_exists(normalized_table):
        return None, None, _dict_error(f"Table not found: {normalized_table}")

    table_columns = _get_table_columns(normalized_table)
    normalized_columns: dict[str, str] = {}
    for kind, raw_name in columns:
        normalized_col, col_error = _normalize_identifier(raw_name, kind)
        if col_error:
            return None, None, col_error
        if normalized_col is None:
            return None, None, _dict_error(f"{kind} must be a non-empty string.")
        if normalized_col not in table_columns:
            return (
                None,
                None,
                _dict_error(
                    f"Column not found: {normalized_col}. Hint: run describe_schema for valid columns."
                ),
            )
        normalized_columns[kind] = normalized_col

    return normalized_table, normalized_columns, None


def _is_numeric_type(column_type: str) -> bool:
    normalized = (column_type or "").upper()
    return any(token in normalized for token in ["INT", "REAL", "FLOA", "DOUB", "NUM"])


def _normalize_max_rows(max_rows: int) -> tuple[int | None, dict[str, Any] | None]:
    if not isinstance(max_rows, int):
        return None, _dict_error("max_rows must be an integer.")
    if max_rows <= 0:
        return None, _dict_error("max_rows must be greater than 0.")
    return min(max_rows, MAX_PLOT_ROWS), None


def _to_numeric(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _get_pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None, _dict_error(
            "matplotlib is required for visualization tools.",
            hint="Install with: uv pip install matplotlib",
        )
    return plt, None


def _new_plot_location() -> tuple[str, Path]:
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    plot_id = uuid4().hex
    return plot_id, PLOTS_DIR / f"{plot_id}.png"


def _register_plot(
    *,
    plot_id: str,
    plot_type: str,
    file_path: Path,
    params: dict[str, Any],
    rows_used: int,
) -> dict[str, Any]:
    metadata = {
        "plot_id": plot_id,
        "plot_type": plot_type,
        "file_path": str(file_path),
        "created_at_iso": _current_timestamp(),
        "params": params,
        "rows_used": rows_used,
    }
    plots[plot_id] = metadata
    return metadata


def _plot_result(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "plot_id": metadata["plot_id"],
        "plot_type": metadata["plot_type"],
        "plot_path": metadata["file_path"],
        "plot_uri": f"plot://{metadata['plot_id']}",
        "rows_used": metadata["rows_used"],
    }


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


@mcp.tool()
def plot_histogram(
    table_name: str,
    column: str,
    bins: int = 30,
    max_rows: int = 20_000,
    title: str | None = None,
) -> dict[str, Any]:
    """Create a histogram PNG for one numeric column in a loaded table."""
    if not isinstance(bins, int) or bins <= 0:
        return _dict_error("bins must be a positive integer.")

    normalized_rows, rows_error = _normalize_max_rows(max_rows)
    if rows_error:
        return rows_error

    normalized_table, normalized_columns, validation_error = _validate_table_and_columns(
        table_name, [("column", column)]
    )
    if validation_error:
        return validation_error

    if normalized_table is None or normalized_columns is None or normalized_rows is None:
        return _dict_error("Invalid histogram request parameters.")

    normalized_column = normalized_columns["column"]
    sql = (
        f"SELECT {_quote_identifier(normalized_column)} AS value "
        f"FROM {_quote_identifier(normalized_table)} "
        f"WHERE {_quote_identifier(normalized_column)} IS NOT NULL "
        f"LIMIT ?"
    )

    try:
        rows = conn.execute(sql, (normalized_rows,)).fetchall()
    except sqlite3.Error as exc:
        return _dict_error(f"SQLite error while reading histogram data: {exc}")

    numeric_values = [
        numeric
        for numeric in (_to_numeric(row["value"]) for row in rows)
        if numeric is not None
    ]
    if not numeric_values:
        return _dict_error("No numeric values available for histogram.")

    plt, plot_error = _get_pyplot()
    if plot_error:
        return plot_error

    fig = None
    try:
        fig, ax = plt.subplots(figsize=DEFAULT_FIGURE_SIZE, dpi=DEFAULT_DPI)
        ax.hist(numeric_values, bins=bins, color="#2563eb", edgecolor="white")
        ax.set_xlabel(normalized_column)
        ax.set_ylabel("Frequency")
        ax.set_title(title or f"Histogram of {normalized_column}")
        fig.tight_layout()

        plot_id, plot_path = _new_plot_location()
        fig.savefig(plot_path, format="png")
    except Exception as exc:
        return _dict_error(f"Unable to render histogram: {exc}")
    finally:
        if fig is not None:
            plt.close(fig)

    metadata = _register_plot(
        plot_id=plot_id,
        plot_type="histogram",
        file_path=plot_path,
        params={
            "table_name": normalized_table,
            "column": normalized_column,
            "bins": bins,
            "max_rows": normalized_rows,
            "title": title,
        },
        rows_used=len(numeric_values),
    )
    return _plot_result(metadata)


@mcp.tool()
def plot_scatter(
    table_name: str,
    x: str,
    y: str,
    max_rows: int = 5_000,
    title: str | None = None,
) -> dict[str, Any]:
    """Create a 2D scatter PNG for two numeric columns."""
    normalized_rows, rows_error = _normalize_max_rows(max_rows)
    if rows_error:
        return rows_error

    normalized_table, normalized_columns, validation_error = _validate_table_and_columns(
        table_name, [("x", x), ("y", y)]
    )
    if validation_error:
        return validation_error

    if normalized_table is None or normalized_columns is None or normalized_rows is None:
        return _dict_error("Invalid scatter request parameters.")

    x_column = normalized_columns["x"]
    y_column = normalized_columns["y"]
    sql = (
        f"SELECT {_quote_identifier(x_column)} AS x_value, {_quote_identifier(y_column)} AS y_value "
        f"FROM {_quote_identifier(normalized_table)} "
        f"WHERE {_quote_identifier(x_column)} IS NOT NULL "
        f"AND {_quote_identifier(y_column)} IS NOT NULL "
        f"LIMIT ?"
    )

    try:
        rows = conn.execute(sql, (normalized_rows,)).fetchall()
    except sqlite3.Error as exc:
        return _dict_error(f"SQLite error while reading scatter data: {exc}")

    xs: list[float] = []
    ys: list[float] = []
    for row in rows:
        xv = _to_numeric(row["x_value"])
        yv = _to_numeric(row["y_value"])
        if xv is None or yv is None:
            continue
        xs.append(xv)
        ys.append(yv)

    if not xs:
        return _dict_error("No numeric pairs available for scatter plot.")

    plt, plot_error = _get_pyplot()
    if plot_error:
        return plot_error

    fig = None
    try:
        fig, ax = plt.subplots(figsize=DEFAULT_FIGURE_SIZE, dpi=DEFAULT_DPI)
        ax.scatter(xs, ys, s=15, alpha=0.55, c="#0f766e")
        ax.set_xlabel(x_column)
        ax.set_ylabel(y_column)
        ax.set_title(title or f"{y_column} vs {x_column}")
        fig.tight_layout()

        plot_id, plot_path = _new_plot_location()
        fig.savefig(plot_path, format="png")
    except Exception as exc:
        return _dict_error(f"Unable to render scatter plot: {exc}")
    finally:
        if fig is not None:
            plt.close(fig)

    metadata = _register_plot(
        plot_id=plot_id,
        plot_type="scatter",
        file_path=plot_path,
        params={
            "table_name": normalized_table,
            "x": x_column,
            "y": y_column,
            "max_rows": normalized_rows,
            "title": title,
        },
        rows_used=len(xs),
    )
    return _plot_result(metadata)


@mcp.tool()
def plot_scatter3d(
    table_name: str,
    x: str,
    y: str,
    z: str,
    color: str | None = None,
    max_rows: int = 5_000,
    title: str | None = None,
    scale: str = "log1p",
) -> dict[str, Any]:
    """Create a 3D scatter PNG from numeric columns with optional z scaling and color channel."""
    normalized_rows, rows_error = _normalize_max_rows(max_rows)
    if rows_error:
        return rows_error

    scale_mode = scale.lower() if isinstance(scale, str) else ""
    if scale_mode not in {"log1p", "none"}:
        return _dict_error("scale must be either 'log1p' or 'none'.")

    column_specs: list[tuple[str, str]] = [("x", x), ("y", y), ("z", z)]
    if color is not None:
        column_specs.append(("color", color))

    normalized_table, normalized_columns, validation_error = _validate_table_and_columns(
        table_name, column_specs
    )
    if validation_error:
        return validation_error

    if normalized_table is None or normalized_columns is None or normalized_rows is None:
        return _dict_error("Invalid scatter3d request parameters.")

    x_column = normalized_columns["x"]
    y_column = normalized_columns["y"]
    z_column = normalized_columns["z"]
    color_column = normalized_columns.get("color")

    select_parts = [
        f"{_quote_identifier(x_column)} AS x_value",
        f"{_quote_identifier(y_column)} AS y_value",
        f"{_quote_identifier(z_column)} AS z_value",
    ]
    where_parts = [
        f"{_quote_identifier(x_column)} IS NOT NULL",
        f"{_quote_identifier(y_column)} IS NOT NULL",
        f"{_quote_identifier(z_column)} IS NOT NULL",
    ]
    if color_column:
        select_parts.append(f"{_quote_identifier(color_column)} AS color_value")

    sql = (
        f"SELECT {', '.join(select_parts)} "
        f"FROM {_quote_identifier(normalized_table)} "
        f"WHERE {' AND '.join(where_parts)} "
        f"LIMIT ?"
    )

    try:
        rows = conn.execute(sql, (normalized_rows,)).fetchall()
    except sqlite3.Error as exc:
        return _dict_error(f"SQLite error while reading 3D scatter data: {exc}")

    x_values: list[float] = []
    y_values: list[float] = []
    z_values: list[float] = []
    colors: list[float] = []

    for row in rows:
        xv = _to_numeric(row["x_value"])
        yv = _to_numeric(row["y_value"])
        zv_raw = _to_numeric(row["z_value"])
        if xv is None or yv is None or zv_raw is None:
            continue

        if scale_mode == "log1p":
            zv = math.copysign(math.log1p(abs(zv_raw)), zv_raw)
        else:
            zv = zv_raw

        x_values.append(xv)
        y_values.append(yv)
        z_values.append(zv)
        if color_column:
            color_value = _to_numeric(row["color_value"])
            colors.append(color_value if color_value is not None else zv)
        else:
            colors.append(zv)

    if not x_values:
        return _dict_error("No numeric triples available for 3D scatter plot.")

    plt, plot_error = _get_pyplot()
    if plot_error:
        return plot_error

    fig = None
    try:
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

        fig = plt.figure(figsize=DEFAULT_FIGURE_SIZE, dpi=DEFAULT_DPI)
        ax = fig.add_subplot(111, projection="3d")
        scatter = ax.scatter(
            x_values,
            y_values,
            z_values,
            c=colors,
            cmap="viridis",
            s=18,
            alpha=0.75,
        )
        ax.set_xlabel(x_column)
        ax.set_ylabel(y_column)
        if scale_mode == "log1p":
            ax.set_zlabel(f"{z_column} (log1p)")
        else:
            ax.set_zlabel(z_column)
        ax.set_title(title or f"3D scatter: {x_column}, {y_column}, {z_column}")
        color_label = color_column if color_column else ("z (scaled)" if scale_mode == "log1p" else "z")
        fig.colorbar(scatter, ax=ax, pad=0.1, shrink=0.7, label=color_label)
        fig.tight_layout()

        plot_id, plot_path = _new_plot_location()
        fig.savefig(plot_path, format="png")
    except Exception as exc:
        return _dict_error(f"Unable to render 3D scatter plot: {exc}")
    finally:
        if fig is not None:
            plt.close(fig)

    metadata = _register_plot(
        plot_id=plot_id,
        plot_type="scatter3d",
        file_path=plot_path,
        params={
            "table_name": normalized_table,
            "x": x_column,
            "y": y_column,
            "z": z_column,
            "color": color_column,
            "max_rows": normalized_rows,
            "title": title,
            "scale": scale_mode,
        },
        rows_used=len(x_values),
    )
    return _plot_result(metadata)


@mcp.tool()
def plot_bar_agg(
    table_name: str,
    group_by: str,
    value: str,
    agg: str = "sum",
    top_n: int = 20,
    title: str | None = None,
) -> dict[str, Any]:
    """Create an aggregated bar chart PNG using GROUP BY over one table."""
    if not isinstance(top_n, int) or top_n <= 0:
        return _dict_error("top_n must be a positive integer.")
    normalized_top_n = min(top_n, MAX_BAR_TOP_N)

    agg_mode = agg.lower() if isinstance(agg, str) else ""
    agg_map = {"sum": "SUM", "avg": "AVG", "count": "COUNT"}
    if agg_mode not in agg_map:
        return _dict_error("agg must be one of: sum, avg, count.")

    normalized_table, normalized_columns, validation_error = _validate_table_and_columns(
        table_name, [("group_by", group_by), ("value", value)]
    )
    if validation_error:
        return validation_error

    if normalized_table is None or normalized_columns is None:
        return _dict_error("Invalid bar aggregation request parameters.")

    group_column = normalized_columns["group_by"]
    value_column = normalized_columns["value"]
    quoted_table = _quote_identifier(normalized_table)
    quoted_group = _quote_identifier(group_column)
    quoted_value = _quote_identifier(value_column)
    agg_fn = agg_map[agg_mode]

    sql = (
        f"SELECT {quoted_group} AS group_label, {agg_fn}({quoted_value}) AS metric_value "
        f"FROM {quoted_table} "
        f"WHERE {quoted_group} IS NOT NULL "
        f"GROUP BY {quoted_group} "
        f"ORDER BY metric_value DESC "
        f"LIMIT ?"
    )

    try:
        rows = conn.execute(sql, (normalized_top_n,)).fetchall()
    except sqlite3.Error as exc:
        return _dict_error(f"SQLite error while reading bar chart data: {exc}")

    labels: list[str] = []
    metrics: list[float] = []
    for row in rows:
        metric = _to_numeric(row["metric_value"])
        if metric is None:
            continue
        labels.append(str(row["group_label"]))
        metrics.append(metric)

    if not labels:
        return _dict_error("No aggregate values available for bar chart.")

    plt, plot_error = _get_pyplot()
    if plot_error:
        return plot_error

    fig = None
    try:
        fig, ax = plt.subplots(figsize=DEFAULT_FIGURE_SIZE, dpi=DEFAULT_DPI)
        x_positions = list(range(len(labels)))
        ax.bar(x_positions, metrics, color="#1d4ed8", alpha=0.9)
        ax.set_ylabel(f"{agg_mode}({value_column})")
        ax.set_title(title or f"{agg_mode.upper()} of {value_column} by {group_column}")
        rotation = 45 if any(len(label) > 12 for label in labels) else 0
        ax.set_xticks(x_positions)
        ax.set_xticklabels(labels, rotation=rotation, ha="right" if rotation else "center")
        fig.tight_layout()

        plot_id, plot_path = _new_plot_location()
        fig.savefig(plot_path, format="png")
    except Exception as exc:
        return _dict_error(f"Unable to render bar chart: {exc}")
    finally:
        if fig is not None:
            plt.close(fig)

    metadata = _register_plot(
        plot_id=plot_id,
        plot_type="bar_agg",
        file_path=plot_path,
        params={
            "table_name": normalized_table,
            "group_by": group_column,
            "value": value_column,
            "agg": agg_mode,
            "top_n": normalized_top_n,
            "title": title,
        },
        rows_used=len(labels),
    )
    return _plot_result(metadata)


@mcp.tool()
def list_plots() -> dict[str, Any]:
    """List generated plots with IDs, paths, and timestamps."""
    items = [
        {
            "plot_id": metadata["plot_id"],
            "plot_type": metadata["plot_type"],
            "plot_path": metadata["file_path"],
            "created_at_iso": metadata["created_at_iso"],
        }
        for metadata in sorted(plots.values(), key=lambda item: item["created_at_iso"], reverse=True)
    ]
    return {"plots": items}


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


@mcp.resource("plots://index", mime_type="application/json")
def plots_index_resource() -> str:
    try:
        index = [
            {
                "plot_id": metadata["plot_id"],
                "plot_type": metadata["plot_type"],
                "file_path": metadata["file_path"],
                "created_at_iso": metadata["created_at_iso"],
                "params": metadata["params"],
                "rows_used": metadata["rows_used"],
            }
            for metadata in sorted(plots.values(), key=lambda item: item["created_at_iso"], reverse=True)
        ]
        return json.dumps({"plots": index}, default=str)
    except Exception as exc:
        return _json_error(f"Unable to produce plots index resource: {exc}")


@mcp.resource("plot://{plot_id}", mime_type="image/png")
def plot_resource(plot_id: str) -> bytes:
    identifier_error = _validate_identifier(plot_id, "plot_id")
    if identifier_error:
        raise ValueError(identifier_error)

    normalized_plot_id = plot_id.strip()
    metadata = plots.get(normalized_plot_id)
    if metadata is None:
        raise ValueError(f"Plot not found: {normalized_plot_id}")

    file_path = Path(metadata["file_path"])
    if not file_path.exists():
        raise ValueError(f"Plot file not found: {file_path}")

    with open(file_path, "rb") as file:
        return file.read()


if __name__ == "__main__":
    mcp.run()
