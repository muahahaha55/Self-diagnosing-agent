#!/usr/bin/env python3
"""Does the served backbone actually emit tool_calls under this parser?

The Block 2 stop rule this implements: a backbone whose tool-call parser is
wrong does not error. It returns prose, the harness records `n_tool_calls=0`,
and every trial looks like a zero-step success -- 30 trials of silent garbage.
So each new backbone answers one trivial tool question before its cells run.

Exit 0 = a real tool call came back. Exit 1 = none (suspect the parser).
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

model = sys.argv[1] if len(sys.argv) > 1 else os.getenv("MODEL")
client = OpenAI(base_url=os.getenv("API_BASE"), api_key=os.getenv("API_KEY", "dummy"))

TOOLS = [{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read a file from the sandbox and return its contents.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": ["path"]},
    },
}]

resp = client.chat.completions.create(
    model=model, temperature=0.0, tools=TOOLS,
    messages=[{"role": "system", "content": "You are a tool-using agent."},
              {"role": "user", "content": "Read the file report.txt and tell me what it says."}],
    extra_body={"chat_template_kwargs": {"enable_thinking": False}},
)
msg = resp.choices[0].message
calls = msg.tool_calls or []
content = msg.content or ""
reasoning = getattr(msg, "reasoning_content", None) or ""

print(f"model            {model}")
print(f"tool_calls       {len(calls)}")
for c in calls:
    print(f"  -> {c.function.name}({c.function.arguments})")
print(f"content          {content[:200]!r}")
print(f"reasoning_content{reasoning[:120]!r}")
leak = [t for t in ("<think>", "</think>") if t in content] or (["reasoning_content"] if reasoning else [])
print(f"thinking leak    {leak or 'none'}")

if not calls:
    print("\nFAIL: no tool_calls. The parser is the first suspect -- the model was "
          "asked a question that has exactly one sane tool answer.")
    sys.exit(1)
print("\nOK: parser produces real tool calls.")
