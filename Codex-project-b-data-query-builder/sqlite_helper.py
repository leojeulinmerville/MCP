"""SQLite helper — database setup and CSV loading."""
import csv
import sqlite3


def create_db() -> sqlite3.Connection:
    """Create an in-memory SQLite database."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _is_int(v: str) -> bool:
    try:
        int(v)
        return True
    except ValueError:
        return False


def _is_float(v: str) -> bool:
    try:
        float(v)
        return True
    except ValueError:
        return False


def _cast(value: str, col_type: str):
    """Cast a CSV string value to the detected column type."""
    if not value:
        return None
    if col_type == "INTEGER":
        try:
            return int(value)
        except ValueError:
            return value
    if col_type == "REAL":
        try:
            return float(value)
        except ValueError:
            return value
    return value


def _read_csv_with_fallback(file_path: str) -> tuple[list[dict[str, str]], str, bool]:
    """Read CSV rows using a robust encoding fallback strategy."""
    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin-1")
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                return list(reader), encoding, False
        except UnicodeDecodeError:
            continue

    with open(file_path, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader), "utf-8 (errors=replace)", True


def load_csv_to_table(conn, file_path: str, table_name: str) -> dict:
    """Load a CSV into a SQLite table. Auto-detects column types.
    Returns: {"table_name": str, "columns": [...], "row_count": int}"""
    rows, encoding_used, used_replacement = _read_csv_with_fallback(file_path)
    if not rows:
        raise ValueError(f"CSV file is empty: {file_path}")

    # Auto-detect types from first 100 rows
    columns = {}
    for col in rows[0].keys():
        sample = [r[col] for r in rows[:100] if r[col]]
        if all(_is_int(v) for v in sample):
            columns[col] = "INTEGER"
        elif all(_is_float(v) for v in sample):
            columns[col] = "REAL"
        else:
            columns[col] = "TEXT"

    col_defs = ", ".join(f'"{col}" {typ}' for col, typ in columns.items())
    conn.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs})')
    placeholders = ", ".join("?" for _ in columns)
    col_names = ", ".join(f'"{c}"' for c in columns)
    for row in rows:
        values = [_cast(row[c], columns[c]) for c in columns]
        conn.execute(f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})', values)
    conn.commit()
    return {
        "table_name": table_name,
        "columns": list(columns.items()),
        "row_count": len(rows),
        "encoding_used": encoding_used,
        "replacement_characters_possible": used_replacement,
    }
