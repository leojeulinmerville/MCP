# Build Your First MCP Server in Python (FastMCP) - Day 1

This project is a minimal MCP server for use with Codex CLI.

## 1) Verify Python version

Python must be `>= 3.10`.

```powershell
python --version
```

## 2) Install uv

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Optional macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 3) Create venv and install dependencies

From the project folder:

```powershell
uv venv
.\.venv\Scripts\activate
uv pip install "mcp[cli]"
```

Optional macOS/Linux activation:

```bash
source .venv/bin/activate
```

## 4) Test with MCP Inspector

```powershell
mcp dev server.py
```

In MCP Inspector, verify:
- Tools include `hello`, `add`, `word_count`
- Resource includes `info:/server`
- `hello` returns `Hello, <name>! The server is working.`
- `add` returns `<a> + <b> = <sum>`
- `word_count` returns `Words: X, Chars: Y, Sentences: Z`

## 5) Connect from Codex CLI (stdio MCP)

Make sure Codex CLI is installed and available as `codex`.

Add the MCP server:

```powershell
codex mcp add my-server -- "<ABS_PATH_TO_PYTHON_EXE>" "<ABS_PATH_TO_server.py>"
```

Windows example:

```powershell
codex mcp add my-server -- "C:\Users\you\my-mcp-server\.venv\Scripts\python.exe" "C:\Users\you\my-mcp-server\server.py"
```

Placeholder notes:
- `<ABS_PATH_TO_PYTHON_EXE>` is your virtual environment interpreter path
- `<ABS_PATH_TO_server.py>` is the absolute path to this `server.py`

Confirm in Codex:
- Start Codex with `codex`
- Run `/mcp` in the TUI
- Confirm `my-server` is listed and enabled

Example prompts in Codex:
- `Use the my-server MCP tool hello with name "class".`
- `Use the my-server MCP tool word_count on: "Hello world. This is Day 1!"`

## 6) Common issues

- Wrong Python interpreter causes `ModuleNotFoundError: No module named 'mcp'`
- Paths must be absolute (do not use relative paths in `codex mcp add`)
- If tools/resources do not refresh, run `codex mcp list`, then restart Codex after MCP config changes
