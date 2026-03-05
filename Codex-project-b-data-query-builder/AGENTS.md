Project B MCP workflow (Codex client instructions)

At the start of every session, read the MCP resource:
server: data-query-builder
uri: prompt:/system

Treat the returned text as the system instructions for how to use the tools.
Then proceed with the task using the MCP tools and cite tool outputs.

If the MCP server is not active, ask the user to enable it and retry reading prompt:/system.