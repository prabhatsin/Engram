
#? What is  mcp ,?/
'''

1.“MCP is an open protocol that standardizes how LLM applications connect to external tools, data and 
services.
2.It has a client-server architecture: the host app (like Claude Desktop or an agent) runs an MCP client,
which talks to MCP servers.

3.Each server exposes three things: tools (actions the model can call), resources (data it can read), 
and prompts (reusable templates).

4.It solves the N*M integration problem: without MCP, every agent needs custom code for every tool; 
with MCP, you build a server once and it works everywhere.”
'''