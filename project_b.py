import csv
import sqlite3
import json
import os
from mcp.server.fastmcp import FastMCP

# Create the MCP server
mcp = FastMCP("Data Query Builder", dependencies=["mcp[cli]"])

# Global state for database connection and query history
conn = None
query_history = []

def create_db() -> sqlite3.Connection:
    """Create an in-memory SQLite database."""
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

# Initialize the global connection
conn = create_db()

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
        return int(value)
    if col_type == "REAL":
        return float(value)
    return value

@mcp.tool()
def load_csv(file_path: str, table_name: str) -> str:
    """
    Load a strictly formatted CSV file from the filesystem into a new in-memory SQLite table.
    This tool automatically detects the column data types (INTEGER, REAL, TEXT).
    Use this tool as the primary way to ingest raw data into the database before analysis.
    
    Args:
        file_path (str): The absolute or relative path to the CSV file.
        table_name (str): The name of the table to create in the database.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            if not rows:
                return f"Error: CSV file is empty: {file_path}"

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
            
            result = {
                "message": f"Successfully loaded CSV into table '{table_name}'.",
                "table_name": table_name, 
                "columns": list(columns.items()), 
                "row_count": len(rows)
            }
            return json.dumps(result, indent=2)
            
    except Exception as e:
        return f"Error loading CSV: {str(e)}"

@mcp.tool()
def describe_schema() -> str:
    """
    List all tables currently in the database along with their columns and data types.
    Use this tool immediately after loading a dataset to understand the exact schema
    before writing any SQL queries or attempting statistical analysis.
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row["name"] for row in cursor.fetchall()]
        
        schema_info = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info(\"{table}\");")
            columns = cursor.fetchall()
            schema_info[table] = [{"cid": col["cid"], "name": col["name"], "type": col["type"]} for col in columns]
            
        return json.dumps(schema_info, indent=2)
    except Exception as e:
        return f"Error describing schema: {str(e)}"

@mcp.tool()
def run_query(sql: str, limit: int = 50) -> str:
    """
    Execute a custom read-only SQL (SELECT) query against the SQLite database and return the results.
    Use this tool when you need to perform complex filtering, grouping (GROUP BY), or joining
    that cannot be answered by the get_statistics or get_unique_values tools.
    Rejects queries containing DROP, DELETE, ALTER, INSERT, UPDATE, CREATE.
    
    Args:
        sql (str): The SELECT query to execute.
        limit (int): The maximum number of rows to return (default 50).
    """
    # Security check for read-only
    sql_upper = sql.upper()
    forbidden_keywords = ["DROP ", "DELETE ", "ALTER ", "INSERT ", "UPDATE ", "CREATE "]
    for kw in forbidden_keywords:
        if kw in sql_upper:
            return f"Error: Forbidden keyword '{kw.strip()}' detected. Only read-only (SELECT) queries are allowed."
            
    try:
        # Append LIMIT if the query does not already have one
        if "LIMIT " not in sql_upper:
            # Simple check, real SQL parsers are better
            sql = f"{sql} LIMIT {limit}"
            
        query_history.append(sql)
            
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        # Convert sqlite3.Row objects to dicts
        result = [dict(row) for row in rows]
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error executing query: {str(e)}"

@mcp.tool()
def get_statistics(table_name: str, column: str) -> str:
    """
    Calculate mathematical summary statistics for a specific column in a table.
    Returns the total rows, non-null count, min, max, and mean.
    Use this tool to quickly understand numeric distributions without having to write SQL.
    Note: 'mean' only applies to numeric columns (INTEGER or REAL).
    
    Args:
        table_name (str): The table to analyze.
        column (str): The column to generate statistics for.
    """
    try:
        # First verify table and column exist to prevent basic SQL injection issues
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        if not cursor.fetchone():
            return f"Error: Table '{table_name}' does not exist."
            
        cursor.execute(f"PRAGMA table_info(\"{table_name}\");")
        columns = [col["name"] for col in cursor.fetchall()]
        if column not in columns:
            return f"Error: Column '{column}' does not exist in table '{table_name}'."
            
        # Get statistics
        sql = f'''
        SELECT 
            COUNT(*) as total_rows,
            COUNT("{column}") as non_null_count,
            MIN("{column}") as min_val,
            MAX("{column}") as max_val,
            AVG(CAST("{column}" AS REAL)) as mean_val
        FROM "{table_name}"
        '''
        cursor.execute(sql)
        row = cursor.fetchone()
        
        stats = dict(row)
        stats["null_count"] = stats["total_rows"] - stats["non_null_count"]
        
        return json.dumps(stats, indent=2)
    except Exception as e:
        return f"Error getting statistics: {str(e)}"

@mcp.tool()
def get_unique_values(table_name: str, column: str, limit: int = 50) -> str:
    """
    Get a list of unique (distinct) entries for a specific column in a table.
    Use this tool to understand categorical data, find exact spellings, or see the domains
    of a column before writing WHERE clauses in SQL.
    
    Args:
        table_name (str): The table to query.
        column (str): The column to get unique values for.
        limit (int): The maximum number of distinct values to return (default 50).
    """
    try:
        # Verify table and column exist
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        if not cursor.fetchone():
            return f"Error: Table '{table_name}' does not exist."
            
        cursor.execute(f"PRAGMA table_info(\"{table_name}\");")
        columns = [col["name"] for col in cursor.fetchall()]
        if column not in columns:
            return f"Error: Column '{column}' does not exist in table '{table_name}'."
            
        sql = f'SELECT DISTINCT "{column}" FROM "{table_name}" WHERE "{column}" IS NOT NULL LIMIT {limit}'
        cursor.execute(sql)
        
        # Extract the single column values into a simple list
        values = [row[column] for row in cursor.fetchall()]
        
        result = {
            "table": table_name,
            "column": column,
            "unique_values": values,
            "count_returned": len(values)
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error getting unique values: {str(e)}"

@mcp.tool()
def list_tables() -> str:
    """
    Retrieve a list of all tables currently loaded in the database, along with their total row counts.
    Use this tool to verify that your data was successfully loaded and to see what tables exist.
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row["name"] for row in cursor.fetchall()]
        
        result = {}
        for table in tables:
            cursor.execute(f'SELECT COUNT(*) as count FROM "{table}";')
            count = cursor.fetchone()["count"]
            result[table] = count
            
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error listing tables: {str(e)}"

@mcp.tool()
def preview_table(table_name: str, rows: int = 5) -> str:
    """
    Preview the first few rows (like Pandas head()) of a specific table.
    Use this tool after loading data to visually verify the formatting and content
    of the table before running in-depth queries.
    
    Args:
        table_name (str): The table to preview.
        rows (int): Number of rows to return (default 5).
    """
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table_name,))
        if not cursor.fetchone():
            return f"Error: Table '{table_name}' does not exist."
            
        sql = f'SELECT * FROM "{table_name}" LIMIT {rows}'
        cursor.execute(sql)
        result = [dict(row) for row in cursor.fetchall()]
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error previewing table: {str(e)}"

@mcp.tool()
def clean_csv(input_path: str, output_path: str) -> str:
    """
    Read a potentially messy CSV file from the filesystem, detect its dialect (separators like ; or \t), 
    and write a cleaned version with standard comma separators and UTF-8 encoding.
    Use this tool on raw CSV files before using load_csv to prevent parsing errors mapping.
    
    Args:
        input_path (str): The path to the original CSV file.
        output_path (str): The path to save the cleaned CSV file.
    """
    try:
        with open(input_path, 'r', encoding='utf-8', errors='replace') as infile:
            sample = infile.read(4096)
            infile.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
            except csv.Error:
                # Fallback to comma if sniffing fails
                dialect = csv.excel
                
            reader = csv.reader(infile, dialect)
            headers = next(reader, None)
            
            if not headers:
                return f"Error: CSV file is empty or invalid: {input_path}"
                
            # Clean headers (strip whitespace)
            headers = [h.strip() for h in headers]
            csv_rows = [headers]
            for row in reader:
                csv_rows.append([col.strip() for col in row])
                
        with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(outfile, delimiter=',')
            writer.writerows(csv_rows)
            
        return f"Successfully cleaned CSV. Found {len(csv_rows)-1} rows. Saved standard CSV to: {output_path}"
    except Exception as e:
        return f"Error cleaning CSV: {str(e)}"

@mcp.tool()
def visualize_data(sql_query: str, chart_type: str, x_column: str, y_column: str, output_html_path: str) -> str:
    """
    Execute a read-only SQL query and generate an interactive HTML chart (using Chart.js).
    This tool saves the visualization as an HTML file on the user's local filesystem.
    Use this tool ONLY if the user explicitly asks to visualize, chart, or graph the data.
    
    Args:
        sql_query (str): A read-only SELECT query to get the data for the chart.
        chart_type (str): Type of chart to draw ('bar', 'line', 'pie', 'doughnut').
        x_column (str): The column name from the query results for the X-axis labels.
        y_column (str): The column name from the query results for the Y-axis data.
        output_html_path (str): The absolute path to save the generated .html file.
    """
    # Security check for read-only
    sql_upper = sql_query.upper()
    forbidden_keywords = ["DROP ", "DELETE ", "ALTER ", "INSERT ", "UPDATE ", "CREATE "]
    for kw in forbidden_keywords:
        if kw in sql_upper:
            return f"Error: Forbidden keyword '{kw.strip()}' detected. Only read-only queries are allowed."
            
    try:
        cursor = conn.cursor()
        cursor.execute(sql_query)
        db_rows = cursor.fetchall()
        
        if not db_rows:
            return "Error: Query returned no results to visualize."
            
        # Check if columns exist
        row_dict = dict(db_rows[0])
        if x_column not in row_dict or y_column not in row_dict:
            return f"Error: Columns '{x_column}' or '{y_column}' not found in query results. Available columns: {list(row_dict.keys())}"
            
        labels = [str(row[x_column]) for row in db_rows]
        # Try to convert Y values to float, fallback to 0 if not numeric
        data = []
        for row in db_rows:
            try:
                data.append(float(row[y_column]))
            except (ValueError, TypeError):
                data.append(0)
                
        html_template = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Data Visualization</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body {{ font-family: sans-serif; text-align: center; background-color: #f4f4f9; padding: 20px; }}
                .chart-container {{ width: 80%; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            </style>
        </head>
        <body>
            <div class="chart-container">
                <canvas id="myChart"></canvas>
            </div>
            <script>
                const ctx = document.getElementById('myChart').getContext('2d');
                new Chart(ctx, {{
                    type: '{chart_type}',
                    data: {{
                        labels: {json.dumps(labels)},
                        datasets: [{{
                            label: '{y_column} by {x_column}',
                            data: {json.dumps(data)},
                            backgroundColor: [
                                'rgba(255, 99, 132, 0.5)',
                                'rgba(54, 162, 235, 0.5)',
                                'rgba(255, 206, 86, 0.5)',
                                'rgba(75, 192, 192, 0.5)',
                                'rgba(153, 102, 255, 0.5)',
                                'rgba(255, 159, 64, 0.5)'
                            ],
                            borderColor: [
                                'rgba(255, 99, 132, 1)',
                                'rgba(54, 162, 235, 1)',
                                'rgba(255, 206, 86, 1)',
                                'rgba(75, 192, 192, 1)',
                                'rgba(153, 102, 255, 1)',
                                'rgba(255, 159, 64, 1)'
                            ],
                            borderWidth: 1
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        plugins: {{
                            title: {{ display: true, text: 'Chart: {chart_type.capitalize()}' }}
                        }}
                    }}
                }});
            </script>
        </body>
        </html>
        '''
        
        with open(output_html_path, 'w', encoding='utf-8') as f:
            f.write(html_template)
            
        return f"Successfully generated a {chart_type} chart. Saved to HTML file: {os.path.abspath(output_html_path)}"
        
    except Exception as e:
        return f"Error generating visualization: {str(e)}"

# Resources

@mcp.resource("db://schema")
def get_db_schema() -> str:
    """Current database schema as JSON."""
    return describe_schema()
    
@mcp.resource("db://query-history")
def get_query_history() -> str:
    """Queries executed this session."""
    return json.dumps(query_history, indent=2)

if __name__ == "__main__":
    mcp.run()
