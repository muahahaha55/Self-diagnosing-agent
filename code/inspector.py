"""
Out-of-band ground-truth inspector for the fs testbed. Version 2.

Why v2: a hash-level diff reports "report.txt was modified" whether the tool
appended or overwrote. That collapses drift operator D1 into the clean
condition and makes the trial unusable for attribution. v2 keeps the hash tier
and adds a content tier that names the KIND of change.

Tiers:
  tier 1  path level    - created / deleted / modified
  tier 2  content level - for each modified path, how it changed

Deliberately NOT added: semantic or embedding-level comparison. Two texts that
are semantically close can still drive different downstream actions, so a
similarity score would blur exactly the distinction we are trying to measure.
String-level classification is the right resolution for this testbed.

The agent never sees any of this.
"""

import hashlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SANDBOX = ROOT / "sandbox"

PREVIEW = 200          # chars kept per side in the log
BIG_FILE = 200_000     # above this we skip storing text


# ----------------------------------------------------------------- lifecycle
def reset(seed: dict[str, str] | None = None) -> None:
    """Wipe and re-seed. Same seed must give a byte-identical world, or
    pass^k and cross-condition comparisons stop meaning anything."""
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    SANDBOX.mkdir(parents=True)
    for path, content in (seed or {}).items():
        fp = SANDBOX / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")


def snapshot() -> dict[str, dict]:
    """True world state. Includes dotfiles and .trash, so soft-delete drift
    stays visible. Each entry carries a hash and, when small enough, the text."""
    state: dict[str, dict] = {}
    for fp in sorted(SANDBOX.rglob("*")):
        if not fp.is_file():
            continue
        rel = fp.relative_to(SANDBOX).as_posix()
        raw = fp.read_bytes()
        entry = {
            "sha": hashlib.sha1(raw).hexdigest()[:12],
            "size": len(raw),
        }
        if len(raw) <= BIG_FILE:
            entry["text"] = raw.decode("utf-8", errors="replace")
        state[rel] = entry
    return state


# ------------------------------------------------------------- content tier
def classify_change(before: str | None, after: str | None) -> str:
    """Name the kind of content change. This is what separates an append-drift
    from an ordinary overwrite when both look like 'modified' at hash level."""
    if before is None or after is None:
        return "unknown"
    if before == after:
        return "unchanged"
    if not before:
        return "filled_from_empty"
    if not after:
        return "emptied"
    if after.startswith(before):
        return "appended"          # D1 signature
    if after.endswith(before):
        return "prepended"
    if before.startswith(after):
        return "truncated"
    if before in after:
        return "wrapped"           # old content survives, embedded
    return "replaced"              # documented write_file behaviour


def _clip(s: str | None) -> str | None:
    if s is None:
        return None
    return s if len(s) <= PREVIEW else s[:PREVIEW] + f"...(+{len(s)-PREVIEW})"


# ------------------------------------------------------------------- diff
def diff(before: dict[str, dict], after: dict[str, dict]) -> dict:
    """Observed effect: what actually changed in the world.

    'modified' stays a plain list of paths so existing callers keep working.
    'modified_detail' carries the tier-2 information.
    """
    b, a = set(before), set(after)
    created = sorted(a - b)
    deleted = sorted(b - a)

    modified, detail = [], []
    for k in sorted(a & b):
        if before[k]["sha"] == after[k]["sha"]:
            continue
        modified.append(k)
        bt, at = before[k].get("text"), after[k].get("text")
        detail.append(
            {
                "path": k,
                "change_kind": classify_change(bt, at),
                "size_before": before[k]["size"],
                "size_after": after[k]["size"],
                "before_preview": _clip(bt),
                "after_preview": _clip(at),
            }
        )

    created_detail = [
        {"path": k, "size": after[k]["size"], "preview": _clip(after[k].get("text"))}
        for k in created
    ]

    return {
        "created": created,
        "deleted": deleted,
        "modified": modified,
        "modified_detail": detail,
        "created_detail": created_detail,
        "unchanged_count": len(
            [k for k in (a & b) if before[k]["sha"] == after[k]["sha"]]
        ),
    }


def is_empty_effect(d: dict) -> bool:
    return not (d["created"] or d["deleted"] or d["modified"])


def summarize(d: dict) -> str:
    """One-line human-readable effect, for console output during trials."""
    parts = []
    if d["created"]:
        parts.append("+" + ",".join(d["created"]))
    if d["deleted"]:
        parts.append("-" + ",".join(d["deleted"]))
    for m in d["modified_detail"]:
        parts.append(f"~{m['path']}[{m['change_kind']}]")
    return " ".join(parts) if parts else "(no effect)"