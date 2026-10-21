
"""Sync bridge to GitHub's MCP server. The only file that imports the MCP SDK."""
import asyncio
import concurrent.futures
import os
import threading

from .. import config

URL = "https://api.githubcopilot.com/mcp/"


class MCPError(Exception):
    pass


def _text_of(result):
    """Join the text parts of a tool result. Raise if the server flagged an error."""
    text = "\n".join(c.text for c in result.content if getattr(c, "type", "") == "text")
    if result.isError:
        raise MCPError(text or "tool reported an error")
    if len(text) > config.MAX_MCP_OUTPUT_CHARS:
        text = text[:config.MAX_MCP_OUTPUT_CHARS] + "\n...[output truncated]"
    return text


class GitHubMCP:
    def __init__(self, token=None, url=URL):
        self._token = token or os.environ.get("GITHUB_TOKEN")
        self._url = url
        self._loop = None
        self._stop = None
        self._session = None
        self._thread = None
        self._ready = threading.Event()
        self._error = None

    def start(self):
        if not self._token:
            raise MCPError("GITHUB_TOKEN is missing")
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()
        if not self._ready.wait(config.MCP_START_TIMEOUT):
            raise MCPError("timed out connecting to the GitHub MCP server")
        if self._error:
            raise MCPError(self._error)

    def _thread_main(self):
        try:
            asyncio.run(self._main())
        except Exception as e:
            self._error = f"{type(e).__name__}: {e}"
        finally:
            self._session = None          # later calls fail with "not connected"
            self._ready.set()             # also unblocks start() if connecting failed

    async def _main(self):
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        self._loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        headers = {"Authorization": f"Bearer {self._token}"}
        async with streamablehttp_client(self._url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self._session = session
                self._ready.set()
                await self._stop.wait()   # keep the connection open until close()

    def _run(self, make_coro):
        if self._session is None:
            raise MCPError("not connected to the GitHub MCP server")
        fut = asyncio.run_coroutine_threadsafe(make_coro(), self._loop)
        try:
            return fut.result(config.MCP_CALL_TIMEOUT)
        except concurrent.futures.TimeoutError:
            fut.cancel()
            raise MCPError(f"timed out after {config.MCP_CALL_TIMEOUT}s")
        except Exception as e:
            raise MCPError(f"{type(e).__name__}: {e}") from e

    def list_tools(self):
        res = self._run(lambda: self._session.list_tools())
        return [{"name": t.name, "description": t.description or "",
                 "input_schema": t.inputSchema} for t in res.tools]

    def call_tool(self, name, args):
        res = self._run(lambda: self._session.call_tool(name, args))
        return _text_of(res)

    def close(self):
        try:
            if self._loop and self._stop:
                self._loop.call_soon_threadsafe(self._stop.set)
        except RuntimeError:
            pass                           # loop already closed
        if self._thread:
            self._thread.join(timeout=5)
        self._session = None