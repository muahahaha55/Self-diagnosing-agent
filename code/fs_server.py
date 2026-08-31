"""
Filesystem MCP server, testbed version.

Design invariants that protect experimental validity:
  1. The tool list is IDENTICAL in every condition (clean, drift, halluc).
     Drift changes behaviour only, never which tools exist.
  2. Tool DESCRIPTIONS never change. Drift = the doc the agent reads is no
     longer true of the code. This mirrors real MCP servers, where roughly
     one in eight has a description-code inconsistency.
  3. No reset/inspect tool is exposed. Ground truth lives in inspector.py,
     out of band, where the agent cannot reach it.

FAULT_MODE env var selects the drift operator: none | D1 | D2 | D3 | D4 | D5 | D6 | D7
"""

import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

SANDBOX = Path(__file__).resolve().parent.parent / "sandbox"
SANDBOX.mkdir(exist_ok=True)

MODE = os.getenv("FAULT_MODE", "none")

mcp = FastMCP("fs")

_locks: set[str] = set()


def _safe(p: str) -> Path:
    fp = (SANDBOX / p).resolve()
    if not str(fp).startswith(str(SANDBOX)):
        raise ValueError(f"Path escapes sandbox: {p}")
    return fp


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file, replacing the file's previous contents if it
    already exists. Creates parent directories as needed."""
    # D4: silent namespace change - everything lands under drafts/
    if MODE == "D4":
        path = f"drafts/{path}"
    # D2: undocumented precondition - a lock must be held first
    if MODE == "D2" and path not in _locks:
        return "ERROR: resource is locked by another process"
    fp = _safe(path)
    fp.parent.mkdir(parents=True, exist_ok=True)
    # D1: silently appends instead of replacing
    if MODE == "D1" and fp.exists():
        fp.write_text(fp.read_text(encoding="utf-8") + content, encoding="utf-8")
    else:
        fp.write_text(content, encoding="utf-8")
    return f"wrote {path}"


@mcp.tool()
def append_file(path: str, content: str) -> str:
    """Append content to the end of a file, preserving what is already there.
    Creates the file if it does not exist."""
    fp = _safe(path)
    fp.parent.mkdir(parents=True, exist_ok=True)
    prev = fp.read_text(encoding="utf-8") if fp.exists() else ""
    # D7: silently applies the append twice
    if MODE == "D7":
        fp.write_text(prev + content + content, encoding="utf-8")
    else:
        fp.write_text(prev + content, encoding="utf-8")
    return f"appended to {path}"


@mcp.tool()
def read_file(path: str) -> str:
    """Return the full text content of a file."""
    # D6: stale cached read - serve the shadow copy under .cache/ if present
    if MODE == "D6":
        cached = SANDBOX / ".cache" / path
        if cached.exists():
            return cached.read_text(encoding="utf-8")
    return _safe(path).read_text(encoding="utf-8")


@mcp.tool()
def list_dir(path: str = ".") -> str:
    """List the names of the entries in a directory, one per line.
    Entries whose name starts with a dot are not shown."""
    fp = _safe(path)
    names = sorted(x.name for x in fp.iterdir() if not x.name.startswith("."))
    # D3: return format changes from bare names to full relative paths
    if MODE == "D3":
        rel = fp.relative_to(SANDBOX).as_posix()
        prefix = "" if rel == "." else rel + "/"
        return "\n".join(f"{prefix}{n}" for n in names)
    return "\n".join(names)


@mcp.tool()
def delete_file(path: str) -> str:
    """Permanently remove a file from the sandbox."""
    fp = _safe(path)
    # D5: soft delete - the file is moved aside, not removed
    if MODE == "D5":
        trash = SANDBOX / ".trash"
        trash.mkdir(exist_ok=True)
        fp.rename(trash / fp.name)
        return f"deleted {path}"
    fp.unlink()
    return f"deleted {path}"


@mcp.tool()
def acquire_lock(path: str) -> str:
    """Acquire an advisory lock on a path. Advisory only: no other tool in
    this server requires a lock to be held."""
    _locks.add(path)
    return f"locked {path}"


if __name__ == "__main__":
    mcp.run()