"""
ReAct-over-MCP agent loop, importable form.

run_task(task, fault_mode) launches the fs server with the given FAULT_MODE,
drives the ReAct loop, and returns the trajectory as a list of dicts.
It does NOT reset or inspect the sandbox - that is the harness's job
(run_trial.py), kept out of band so the agent never sees ground truth.
"""

import os
import json
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "code" / "fs_server.py"

load_dotenv(ROOT / ".env")

API_BASE = os.getenv("API_BASE")
API_KEY = os.getenv("API_KEY", "dummy")
MODEL = os.getenv("MODEL")
MAX_STEPS = 10

client = OpenAI(base_url=API_BASE, api_key=API_KEY)

SYSTEM_PROMPT = (
    "You are a tool-using agent operating on a sandboxed filesystem. "
    "Use the provided tools to complete the user's task. "
    "When the task is fully complete, reply with a short plain-text "
    "confirmation and do not call any more tools."
)


def to_openai_tools(mcp_tools):
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema,
            },
        }
        for t in mcp_tools
    ]


def extract_text(result) -> str:
    return "\n".join(getattr(b, "text", str(b)) for b in result.content)


async def run_task(task: str, fault_mode: str = "none", verbose: bool = True):
    """Run one task under a given fault mode. Returns the trajectory list."""
    server_params = StdioServerParameters(
        command="python",
        args=[str(SERVER)],
        cwd=str(ROOT),
        env={**os.environ, "FAULT_MODE": fault_mode},   # inject drift here
    )

    trajectory = []

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools = to_openai_tools(listed.tools)

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task},
            ]

            for step in range(MAX_STEPS):
                resp = client.chat.completions.create(
                    model=MODEL, messages=messages, tools=tools, temperature=0.0
                )
                msg = resp.choices[0].message

                if not msg.tool_calls:
                    if verbose:
                        print(f"[step {step}] final: {msg.content}")
                    trajectory.append(
                        {"step": step, "belief": None, "predicted_effect": None,
                         "tool": None, "args": None, "raw_result": None,
                         "observed_effect": None, "final_answer": msg.content}
                    )
                    break

                messages.append(msg.model_dump(exclude_none=True))

                for call in msg.tool_calls:
                    name = call.function.name
                    try:
                        args = json.loads(call.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {"_raw": call.function.arguments}

                    try:
                        result = await session.call_tool(name, args)
                        raw = extract_text(result)
                    except Exception as e:
                        raw = f"ERROR: {type(e).__name__}: {e}"

                    if verbose:
                        print(f"[step {step}] {name}({args}) -> {raw}")

                    trajectory.append(
                        {"step": step, "belief": None, "predicted_effect": None,
                         "tool": name, "args": args, "raw_result": raw,
                         "observed_effect": None}
                    )
                    messages.append(
                        {"role": "tool", "tool_call_id": call.id, "content": raw}
                    )
            else:
                if verbose:
                    print(f"[warn] hit MAX_STEPS={MAX_STEPS}")

    return trajectory


# quick manual smoke test: run one clean task
if __name__ == "__main__":
    traj = asyncio.run(
        run_task(
            "Create a file named report.txt containing 'hello', "
            "then read it back and confirm the content.",
            fault_mode="none",
        )
    )
    print(json.dumps(traj, indent=2, ensure_ascii=False))