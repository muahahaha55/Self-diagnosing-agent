import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["code/fs_server.py"],
)

async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("=== Available tools ===")
            for t in tools.tools:
                print(f"- {t.name}: {t.description}")

            print("\n=== Manual call: write_file ===")
            result = await session.call_tool(
                "write_file",
                {"path": "report.txt", "content": "hello"},
            )
            print(result.content[0].text)

            print("\n=== Manual call: read_file ===")
            result = await session.call_tool(
                "read_file",
                {"path": "report.txt"},
            )
            print(result.content[0].text)

            print("\n=== Manual call: list_dir ===")
            result = await session.call_tool("list_dir", {"path": "."})
            print(result.content[0].text)

if __name__ == "__main__":
    asyncio.run(main())