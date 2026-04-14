from fastmcp import FastMCP
from app.server.routes import register_tools


class MCPServer:
    def __init__(self):
        self.mcp = FastMCP(
            name="Social MCP Server",
            version="3.1.0"
        )
        register_tools(self.mcp)

    def run(self):
        self.mcp.run()


def create_server():
    return MCPServer()
