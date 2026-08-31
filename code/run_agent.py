"""
ReAct-over-MCP agent loop, importable form. Version 3.

Two additions over v2, both required by Layer 4:

  1. tool_specs are returned. Layer 4's axis A asks whether the tool's own
     description matches what actually happened, so the description must
     survive into the trial record. v2 built the schema and threw it away.

  2. an on_step hook fires after every tool call. The harness uses it to
     snapshot the world between steps, which is what makes per-step effects
     and the early-detection-step metric possible at all. Without it we only
     ever see the effect of the whole task.

The hook is harness-side. The agent still never sees ground truth.
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

# Reasoning toggle. Qwen3.5 thinks by default, emitting a long <think> block
# before every tool call. For simple filesystem tasks this is mostly wasted
# tokens and is the main reason a run is slow. Off = much faster.
#
# CAVEAT for the paper: thinking on vs off is a different agent regime and may
# change belief formation / self-diagnosis behaviour. Use False for fast
# pipeline checks; when producing headline numbers, decide deliberately and
# report which regime was used (or ablate both).
ENABLE_THINKING = False

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


def _thinking_trace(msg) -> str | None:
    """Return whatever reasoning trace this response carried, if any.

    Two shapes exist in the wild: vLLM with a reasoning parser splits the
    reasoning into `reasoning_content`, while without one the raw `<think>`
    block stays inline in `content`. We look for both, because the failure we
    are guarding against (see PROVENANCE.md, "Mandatory Block-2 checklist")
    is exactly the case where enable_thinking=False was accepted and ignored.
    """
    rc = getattr(msg, "reasoning_content", None)
    if rc:
        return rc
    content = msg.content or ""
    if "<think>" in content:
        return content[content.index("<think>"):]
    return None


async def run_task(task: str, fault_mode: str = "none",
                   on_step=None, verbose: bool = True,
                   model: str | None = None, temperature: float = 0.0,
                   seed: int | None = None,
                   enable_thinking: bool | None = None) -> dict:
    """Run one task under a given fault mode.

    on_step(record) is called right after each tool call returns, before the
    next LLM turn. The harness may mutate `record` in place, e.g. to attach
    the true observed_effect for that single step.

    model/temperature/seed override the .env defaults so one process can sweep
    the Block 2 matrix (3 backbones x {0.0, 0.7}; seeds replicated only at
    0.7, since greedy decoding makes re-seeding a near-identical trajectory).

    enable_thinking=None keeps the module default. The flag is only meaningful
    for Qwen3.5 -- Llama-3.1 and Mistral-Nemo have no equivalent toggle and
    vLLM silently ignores an unknown chat_template_kwargs key -- so the return
    value carries `thinking_seen` for the caller to check rather than trusting
    the flag.

    Returns {"trajectory", "tool_specs", "final_answer", "run_config",
             "thinking_seen", "thinking_sample"}
    """
    model = model or MODEL
    if enable_thinking is None:
        enable_thinking = ENABLE_THINKING

    server_params = StdioServerParameters(
        command="python",
        args=[str(SERVER)],
        cwd=str(ROOT),
        env={**os.environ, "FAULT_MODE": fault_mode},
    )

    trajectory = []
    final_answer = None
    thinking_sample = None

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            tools = to_openai_tools(listed.tools)

            # keep the descriptions the agent actually saw
            tool_specs = [
                {"name": t["function"]["name"],
                 "description": t["function"]["description"]}
                for t in tools
            ]

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task},
            ]

            for step in range(MAX_STEPS):
                kwargs = dict(
                    model=model, messages=messages, tools=tools,
                    temperature=temperature, parallel_tool_calls=False,
                    extra_body={"chat_template_kwargs":
                                {"enable_thinking": enable_thinking}},
                )
                # only send `seed` when one was asked for: at temperature 0 the
                # decode is greedy and the field is noise in the log.
                if seed is not None:
                    kwargs["seed"] = seed
                resp = client.chat.completions.create(**kwargs)
                msg = resp.choices[0].message

                # guard: enable_thinking=False has been silently ignored on
                # some vLLM builds (parameter-name drift between the chat
                # template and the reasoning parser). Record what we actually
                # got so the caller can refuse to trust the run.
                if thinking_sample is None:
                    trace = _thinking_trace(msg)
                    if trace:
                        thinking_sample = trace[:400]

                if not msg.tool_calls:
                    final_answer = msg.content
                    if verbose:
                        print(f"[step {step}] final: {msg.content}")
                    trajectory.append(
                        {"step": step, "belief": None, "predicted_effect": None,
                         "tool": None, "args": None, "raw_result": None,
                         "observed_effect": None, "final_answer": msg.content}
                    )
                    break

                messages.append(msg.model_dump(exclude_none=True))

                # sequential regime: one action per step. If the model
                # still emits several, honour only the first.
                for call in msg.tool_calls[:1]:
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

                    record = {
                        "step": step,
                        "belief": None,            # Layer 1, later
                        "predicted_effect": None,  # Layer 2, later
                        "tool": name,
                        "args": args,
                        "raw_result": raw,
                        "observed_effect": None,   # filled by on_step
                    }

                    if on_step is not None:
                        on_step(record)            # harness snapshots here

                    if verbose:
                        eff = record.get("observed_effect")
                        tail = f" | effect: {eff}" if eff else ""
                        print(f"[step {step}] {name}({args}) -> {raw}{tail}")

                    trajectory.append(record)
                    messages.append(
                        {"role": "tool", "tool_call_id": call.id, "content": raw}
                    )
            else:
                if verbose:
                    print(f"[warn] hit MAX_STEPS={MAX_STEPS}")

    return {
        "trajectory": trajectory,
        "tool_specs": tool_specs,
        "final_answer": final_answer,
        "run_config": {
            "model": model,
            "temperature": temperature,
            "seed": seed,
            "enable_thinking": enable_thinking,
            "max_steps": MAX_STEPS,
        },
        # True => the backbone emitted a reasoning trace despite the flag.
        "thinking_seen": thinking_sample is not None,
        "thinking_sample": thinking_sample,
    }


if __name__ == "__main__":
    out = asyncio.run(
        run_task("Create report.txt containing 'hello', then read it back.",
                 fault_mode="none")
    )
    print(json.dumps(out, indent=2, ensure_ascii=False))