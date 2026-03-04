import json

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-server")


@mcp.tool()
def hello(name: str) -> str:
    return f"Hello, {name}! The server is working."


@mcp.tool()
def add(a: float, b: float) -> str:
    return f"{a} + {b} = {a + b}"


@mcp.resource("info:/server")
def server_info() -> str:
    data = {
        "name": "my-server",
        "version": "1.0.0",
        "tools": ["hello", "add", "word_count"],
    }
    return json.dumps(data)


@mcp.tool()
def word_count(text: str) -> str:
    words = len(text.split())
    chars = len(text)
    sentences = text.count(".") + text.count("!") + text.count("?")
    return f"Words: {words}, Chars: {chars}, Sentences: {sentences}"


if __name__ == "__main__":
    mcp.run()
