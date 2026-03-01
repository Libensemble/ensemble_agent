"""MCP server discovery and connection utilities."""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def find_mcp_server(user_path=None):
    """Locate the generator MCP server file.

    Search order: user_path → GENERATOR_MCP_SERVER env → sibling of package → cwd.
    """
    locations = []
    if user_path:
        locations.append(Path(user_path))

    env_path = os.environ.get("GENERATOR_MCP_SERVER")
    if env_path:
        locations.append(Path(env_path))

    # Sibling to ensemble_agent/ package
    locations.append(Path(__file__).parent.parent / "mcp_server.mjs")
    locations.append(Path.cwd() / "mcp_server.mjs")

    for loc in locations:
        if loc.exists():
            return loc

    print("Error: Cannot find mcp_server.mjs")
    print(f"Searched: {', '.join(str(loc) for loc in locations)}")
    print("Set GENERATOR_MCP_SERVER environment variable or use --mcp-server flag")
    sys.exit(1)


@asynccontextmanager
async def connect_mcp(server_path):
    """Async context manager that yields an initialized MCP ClientSession."""
    suffix = Path(server_path).suffix
    if suffix == ".mjs" or suffix == ".js":
        command, args = "node", [str(server_path)]
    else:
        command, args = "python", [str(server_path)]

    server_params = StdioServerParameters(command=command, args=args)
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session
