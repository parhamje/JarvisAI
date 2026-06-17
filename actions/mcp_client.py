"""
mcp_client.py — Model Context Protocol (MCP) Client for Jarvis
Connects to any MCP server via stdio or SSE transport.
Lets Jarvis call tools from external MCP servers dynamically.

Usage (voice):
  "Jarvis, use MCP to query my SQLite database"
  "Jarvis, connect to the GitHub MCP server and list my repos"

Config: Add servers to config/mcp_servers.json
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    _MCP = True
except ImportError:
    _MCP = False


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


_SERVERS_CONFIG = _base_dir() / "config" / "mcp_servers.json"


def _load_servers() -> dict:
    """Load MCP server configs from config/mcp_servers.json"""
    if not _SERVERS_CONFIG.exists():
        # Create a template config
        template = {
            "_comment": "Add MCP servers here. Each entry needs 'command' and optional 'args'.",
            "example_sqlite": {
                "command": "uvx",
                "args": ["mcp-server-sqlite", "--db-path", "C:/path/to/your.db"],
                "description": "SQLite database access"
            },
            "example_filesystem": {
                "command": "uvx",
                "args": ["mcp-server-filesystem", "C:/Users/parha/Documents"],
                "description": "Local filesystem access"
            }
        }
        _SERVERS_CONFIG.parent.mkdir(parents=True, exist_ok=True)
        _SERVERS_CONFIG.write_text(
            json.dumps(template, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"[MCP] Created template config: {_SERVERS_CONFIG}")
    try:
        return json.loads(_SERVERS_CONFIG.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[MCP] Config load error: {e}")
        return {}


def _run_async(coro, timeout: float = 30.0):
    """Run an async coroutine from sync context in a thread."""
    result = [None]
    error  = [None]

    def runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result[0] = loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
        except Exception as e:
            error[0] = e
        finally:
            loop.close()

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join(timeout=timeout + 2)

    if error[0]:
        raise error[0]
    return result[0]


async def _list_tools_async(server_name: str, server_cfg: dict) -> list[dict]:
    """List all tools available on an MCP server."""
    cmd  = server_cfg.get("command", "")
    args = server_cfg.get("args", [])
    if not cmd:
        raise ValueError(f"No 'command' defined for server '{server_name}'")

    params = StdioServerParameters(command=cmd, args=args)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            return [
                {
                    "name":        t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema if hasattr(t, "inputSchema") else {},
                }
                for t in tools_result.tools
            ]


async def _call_tool_async(server_name: str, server_cfg: dict,
                            tool_name: str, tool_args: dict) -> str:
    """Call a tool on an MCP server and return the text result."""
    cmd  = server_cfg.get("command", "")
    args = server_cfg.get("args", [])
    if not cmd:
        raise ValueError(f"No 'command' defined for server '{server_name}'")

    params = StdioServerParameters(command=cmd, args=args)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, tool_args)

            # Extract text from result content blocks
            parts = []
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                elif isinstance(block, dict) and "text" in block:
                    parts.append(block["text"])
            return "\n".join(parts) if parts else "(no output)"


# ── Public tool entry point ───────────────────────────────────────────────────

def mcp_client(parameters: dict, player=None, speak=None) -> str:
    """
    Jarvis MCP tool — connects to external MCP servers.

    Actions:
      list_servers  — show all configured MCP servers
      list_tools    — list available tools on a server
      call_tool     — execute a tool on a server
      add_server    — add a new MCP server config
    """
    if not _MCP:
        return (
            "The MCP package is not installed, Sir. "
            "Run: .venv\\Scripts\\pip install mcp"
        )

    params  = parameters or {}
    action  = params.get("action", "list_servers").strip().lower()
    servers = _load_servers()
    # Filter out comment keys
    servers = {k: v for k, v in servers.items() if not k.startswith("_")}

    def _log(msg: str):
        print(f"[MCP] {msg}")
        if player:
            player.write_log(f"[mcp] {msg}")

    # ── list_servers ──────────────────────────────────────────────────────────
    if action == "list_servers":
        if not servers:
            return (
                "No MCP servers configured yet, Sir. "
                f"Add them to {_SERVERS_CONFIG}"
            )
        lines = [f"Configured MCP servers ({len(servers)}):"]
        for name, cfg in servers.items():
            desc = cfg.get("description", "")
            cmd  = cfg.get("command", "")
            lines.append(f"  • {name}: {desc or cmd}")
        return "\n".join(lines)

    # ── list_tools ────────────────────────────────────────────────────────────
    if action == "list_tools":
        server_name = params.get("server", "").strip()
        if not server_name:
            return "Please specify which server to list tools from, Sir."
        if server_name not in servers:
            return f"Unknown server '{server_name}'. Known: {', '.join(servers.keys())}"
        try:
            _log(f"Listing tools on '{server_name}'...")
            tools = _run_async(_list_tools_async(server_name, servers[server_name]))
            if not tools:
                return f"No tools found on '{server_name}', Sir."
            lines = [f"Tools on '{server_name}' ({len(tools)}):"]
            for t in tools:
                desc = t.get("description", "")[:80]
                lines.append(f"  • {t['name']}: {desc}")
            return "\n".join(lines)
        except Exception as e:
            return f"Failed to list tools on '{server_name}': {e}"

    # ── call_tool ─────────────────────────────────────────────────────────────
    if action == "call_tool":
        server_name = params.get("server", "").strip()
        tool_name   = params.get("tool", "").strip()
        tool_args   = params.get("args", {})
        if isinstance(tool_args, str):
            try:
                tool_args = json.loads(tool_args)
            except Exception:
                tool_args = {}

        if not server_name:
            return "Please specify which server to use, Sir."
        if not tool_name:
            return "Please specify which tool to call, Sir."
        if server_name not in servers:
            return f"Unknown server '{server_name}'. Known: {', '.join(servers.keys())}"

        try:
            _log(f"Calling {server_name}/{tool_name}({tool_args})...")
            result = _run_async(
                _call_tool_async(server_name, servers[server_name], tool_name, tool_args),
                timeout=45.0
            )
            _log(f"Result ({len(result)} chars)")
            # Truncate very long results for voice
            if len(result) > 800:
                return result[:800] + f"\n...[{len(result) - 800} more chars — full result logged]"
            return result
        except Exception as e:
            return f"Tool call failed: {e}"

    # ── add_server ────────────────────────────────────────────────────────────
    if action == "add_server":
        name    = params.get("name", "").strip()
        command = params.get("command", "").strip()
        args    = params.get("args", [])
        desc    = params.get("description", "").strip()

        if not name or not command:
            return "Please provide both a server name and command, Sir."

        all_cfg = _load_servers()
        all_cfg[name] = {"command": command, "args": args, "description": desc}
        _SERVERS_CONFIG.write_text(
            json.dumps(all_cfg, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        _log(f"Added server '{name}'")
        return f"MCP server '{name}' added, Sir. Use 'list_tools' to see what it can do."

    return (
        f"Unknown MCP action: '{action}'. "
        "Supported: list_servers, list_tools, call_tool, add_server."
    )
