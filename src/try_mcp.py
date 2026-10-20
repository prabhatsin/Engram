import asyncio, os
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()
URL = "https://api.githubcopilot.com/mcp/"
HEADERS = {"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}

async def main():
    async with streamablehttp_client(URL, headers=HEADERS) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            print(len(tools), "tools")
            for t in tools:
                print("-", t.name)

asyncio.run(main())