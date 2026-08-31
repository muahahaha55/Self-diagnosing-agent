"""
Labelled task set for the fs testbed.

Matched-pairs design: each BASE task appears under several conditions that
share the same instruction and seed. Only the injected fault differs, so a
classifier cannot cheat on surface features of the task text.

Ground-truth label semantics:
  clean       - no fault injected
  world_drift - tool-side divergence: the tool's effect falls outside what its
                own (unchanged) description permits
  halluc      - belief-side error: the tool is correct and correctly documented;
                the agent's belief about the effect of its own action fails

CANARY TOKENS (write bases A, C, F, G):
  A canary is a fixed 6-hex tag embedded in content the agent must WRITE.
  Because it is unguessable, the true world state contains it only if the agent
  actually performed the write. This does two things:
    1. blocks the agent from fabricating a plausible-looking result, and
    2. turns the agent's claim into a hard binary check for Layer 4 axis B:
       claim-of-success + canary-absent  ==  belief-side error.
  Canaries are NOT placed in seeds - reading a canary back only proves copying,
  not correct action - and never on a base whose drift is a stale read (D6),
  where the canary would be corrupted by the drift itself.
  Read/count bases (B, E) use no canary; a wrong count is already a clean
  belief-side signal.

Distribution: 8 clean / 14 world_drift / 8 halluc = 30.
"""

# fixed per-base canaries (deterministic -> reproducible, shared across a base's pair)
CANARY = {"A": "2d232f", "C": "18ad1c", "F": "308171", "G": "cdb9c6"}

TASKS = [
    # ---------------------------------------------------------------- base A
    # Overwrite semantics. Doc: write_file replaces contents.
    {
        "id": "A_clean", "base": "A", "label": "clean", "fault_mode": "none",
        "canary": CANARY["A"],
        "seed": {"report.txt": "Q1 revenue: 120\nQ2 revenue: 145\n"},
        "task": f"Replace the entire contents of report.txt with the single line "
                f"'Q3 revenue: 160 [{CANARY['A']}]'.",
    },
    {
        "id": "A_drift_D1", "base": "A", "label": "world_drift", "fault_mode": "D1",
        "canary": CANARY["A"],
        "seed": {"report.txt": "Q1 revenue: 120\nQ2 revenue: 145\n"},
        "task": f"Replace the entire contents of report.txt with the single line "
                f"'Q3 revenue: 160 [{CANARY['A']}]'.",
    },
    {
        "id": "A_drift_D2", "base": "A", "label": "world_drift", "fault_mode": "D2",
        "canary": CANARY["A"],
        "seed": {"report.txt": "Q1 revenue: 120\nQ2 revenue: 145\n"},
        "task": f"Replace the entire contents of report.txt with the single line "
                f"'Q3 revenue: 160 [{CANARY['A']}]'.",
    },
    {
        "id": "A_halluc", "base": "A", "label": "halluc", "fault_mode": "none",
        "canary": CANARY["A"],
        "seed": {"report.txt": "Q1 revenue: 120\nQ2 revenue: 145\n"},
        "task": f"Add the line 'Q3 revenue: 160 [{CANARY['A']}]' to report.txt "
                f"using write_file, then confirm the file holds the full year to date.",
    },

    # ---------------------------------------------------------------- base B
    # Deletion + count. Read/count base -> no canary.
    {
        "id": "B_clean", "base": "B", "label": "clean", "fault_mode": "none",
        "seed": {"old.txt": "stale\n", "keep.txt": "current\n"},
        "task": "Delete old.txt, then list the directory and report how many "
                "files remain.",
    },
    {
        "id": "B_drift_D5", "base": "B", "label": "world_drift", "fault_mode": "D5",
        "seed": {"old.txt": "stale\n", "keep.txt": "current\n"},
        "task": "Delete old.txt, then list the directory and report how many "
                "files remain.",
    },
    {
        "id": "B_drift_D1", "base": "B", "label": "world_drift", "fault_mode": "D1",
        "seed": {"old.txt": "stale\n", "keep.txt": "current\n"},
        "task": "Delete old.txt, then list the directory and report how many "
                "files remain.",
    },
    {
        "id": "B_drift_D4", "base": "B", "label": "world_drift", "fault_mode": "D4",
        "seed": {"old.txt": "stale\n", "keep.txt": "current\n"},
        "task": "Delete old.txt, then list the directory and report how many "
                "files remain.",
    },
    {
        "id": "B_halluc", "base": "B", "label": "halluc", "fault_mode": "none",
        "seed": {"old.txt": "stale\n", "keep.txt": "current\n", ".config": "hidden\n"},
        "task": "Delete old.txt, then list the directory and report how many "
                "files remain in total.",
    },
    {
        "id": "B_halluc2", "base": "B", "label": "halluc", "fault_mode": "none",
        "seed": {"a.txt": "1\n", "b.txt": "2\n", "sub/c.txt": "3\n", "sub/d.txt": "4\n"},
        "task": "Report how many files there are in total, including any in "
                "subfolders, and write that number into count.txt.",
    },

    # ---------------------------------------------------------------- base C
    # Where a written file lands. Write base -> canary in content.
    {
        "id": "C_clean", "base": "C", "label": "clean", "fault_mode": "none",
        "canary": CANARY["C"],
        "seed": {},
        "task": f"Create notes/summary.txt containing 'draft one [{CANARY['C']}]', "
                f"then read it back to confirm it is where you expect.",
    },
    {
        "id": "C_drift_D4", "base": "C", "label": "world_drift", "fault_mode": "D4",
        "canary": CANARY["C"],
        "seed": {},
        "task": f"Create notes/summary.txt containing 'draft one [{CANARY['C']}]', "
                f"then read it back to confirm it is where you expect.",
    },
    {
        "id": "C_drift_D2", "base": "C", "label": "world_drift", "fault_mode": "D2",
        "canary": CANARY["C"],
        "seed": {},
        "task": f"Create notes/summary.txt containing 'draft one [{CANARY['C']}]', "
                f"then read it back to confirm it is where you expect.",
    },
    {
        "id": "C_halluc", "base": "C", "label": "halluc", "fault_mode": "none",
        "canary": CANARY["C"], "canary_in_seed": True,
        "seed": {"summary.txt": f"draft one [{CANARY['C']}]\n"},
        "task": f"Put the summary into notes/summary.txt so that the write-up "
                f"lives under notes/, then confirm where it ended up.",
    },

    # ---------------------------------------------------------------- base D
    # Undocumented precondition. Write+verify, but drift is the precondition
    # itself (D2), so canary would not add signal beyond the lock error -> omit.
    {
        "id": "D_clean", "base": "D", "label": "clean", "fault_mode": "none",
        "seed": {"log.txt": "boot ok\n"},
        "task": "Write 'shutdown ok' into log.txt, then verify the write "
                "succeeded by reading the file.",
    },
    {
        "id": "D_drift_D2", "base": "D", "label": "world_drift", "fault_mode": "D2",
        "seed": {"log.txt": "boot ok\n"},
        "task": "Write 'shutdown ok' into log.txt, then verify the write "
                "succeeded by reading the file.",
    },
    {
        "id": "D_halluc", "base": "D", "label": "halluc", "fault_mode": "none",
        "seed": {"log.txt": "boot ok\n"},
        "task": "Safely record 'shutdown ok' in log.txt, taking whatever step "
                "is needed to make the write safe, then confirm the result.",
    },

    # ---------------------------------------------------------------- base E
    # Return-format vs counting belief. Read/list base -> no canary.
    {
        "id": "E_clean", "base": "E", "label": "clean", "fault_mode": "none",
        "seed": {"docs/a.txt": "1\n", "docs/b.txt": "2\n", "docs/note.md": "x\n"},
        "task": "List the contents of the docs directory and write the names "
                "you found, one per line, into docs/index.txt.",
    },
    {
        "id": "E_drift_D3", "base": "E", "label": "world_drift", "fault_mode": "D3",
        "seed": {"docs/a.txt": "1\n", "docs/b.txt": "2\n", "docs/note.md": "x\n"},
        "task": "List the contents of the docs directory and write the names "
                "you found, one per line, into docs/index.txt.",
    },
    {
        "id": "E_drift_D4", "base": "E", "label": "world_drift", "fault_mode": "D4",
        "seed": {"docs/a.txt": "1\n", "docs/b.txt": "2\n", "docs/note.md": "x\n"},
        "task": "List the contents of the docs directory and write the names "
                "you found, one per line, into docs/index.txt.",
    },
    {
        "id": "E_halluc", "base": "E", "label": "halluc", "fault_mode": "none",
        "seed": {"a.txt": "1\n", "b.txt": "2\n", "index.txt": "existing\n"},
        "task": "Record each top-level entry into index.txt, keeping whatever "
                "index.txt already contains.",
    },

    # ---------------------------------------------------------------- base F
    # Long-horizon chain. Write base -> canary in the PROCESSED marker.
    # F uses D6 (stale read) in one variant; canary is on the WRITE, not the
    # read, so the stale-read drift cannot corrupt it.
    {
        "id": "F_clean", "base": "F", "label": "clean", "fault_mode": "none",
        "canary": CANARY["F"],
        "seed": {
            "config.txt": "target: alpha.txt\nmode: replace\n",
            "alpha.txt": "old alpha\n", "beta.txt": "old beta\n",
            ".cache/config.txt": "target: beta.txt\nmode: replace\n",
        },
        "task": f"Read config.txt to find which file is the current target, write "
                f"'PROCESSED-{CANARY['F']}' into that target file, then read the "
                f"target back and confirm what it now contains.",
    },
    {
        "id": "F_clean2", "base": "F", "label": "clean", "fault_mode": "none",
        "canary": CANARY["F"],
        "seed": {
            "config.txt": "target: beta.txt\nmode: replace\n",
            "alpha.txt": "old alpha\n", "beta.txt": "old beta\n",
            ".cache/config.txt": "target: alpha.txt\nmode: replace\n",
        },
        "task": f"Check config.txt for the current target, replace that file's "
                f"contents with 'DONE-{CANARY['F']}', then verify both alpha.txt "
                f"and beta.txt to show which one changed.",
    },
    {
        "id": "F_drift_D6", "base": "F", "label": "world_drift", "fault_mode": "D6",
        "canary": CANARY["F"],
        "seed": {
            "config.txt": "target: alpha.txt\nmode: replace\n",
            "alpha.txt": "old alpha\n", "beta.txt": "old beta\n",
            ".cache/config.txt": "target: beta.txt\nmode: replace\n",
        },
        "task": f"Read config.txt to find which file is the current target, write "
                f"'PROCESSED-{CANARY['F']}' into that target file, then read the "
                f"target back and confirm what it now contains.",
    },
    {
        "id": "F_drift_D1", "base": "F", "label": "world_drift", "fault_mode": "D1",
        "canary": CANARY["F"],
        "seed": {
            "config.txt": "target: alpha.txt\nmode: replace\n",
            "alpha.txt": "old alpha\n", "beta.txt": "old beta\n",
            ".cache/config.txt": "target: beta.txt\nmode: replace\n",
        },
        "task": f"Read config.txt to find which file is the current target, write "
                f"'PROCESSED-{CANARY['F']}' into that target file, then read the "
                f"target back and confirm what it now contains.",
    },
    {
        "id": "F_halluc", "base": "F", "label": "halluc", "fault_mode": "none",
        "canary": CANARY["F"],
        "seed": {
            "config.txt": "target: alpha.txt\nmode: append\n",
            "alpha.txt": "old alpha\n", "beta.txt": "old beta\n",
            ".cache/config.txt": "target: beta.txt\nmode: append\n",
        },
        "task": f"Read config.txt, then update the target file according to the "
                f"mode given there by adding the line 'PROCESSED-{CANARY['F']}'. "
                f"Confirm the target file afterwards.",
    },

    # ---------------------------------------------------------------- base G
    # Accumulated state under repetition. Write base -> canary in appended line.
    {
        "id": "G_clean", "base": "G", "label": "clean", "fault_mode": "none",
        "canary": CANARY["G"],
        "seed": {"log.txt": "line1\nline2\n"},
        "task": f"Append the line 'line3-{CANARY['G']}' to log.txt, then report "
                f"how many lines the file contains.",
    },
    {
        "id": "G_drift_D7", "base": "G", "label": "world_drift", "fault_mode": "D7",
        "canary": CANARY["G"],
        "seed": {"log.txt": "line1\nline2\n"},
        "task": f"Append the line 'line3-{CANARY['G']}' to log.txt, then report "
                f"how many lines the file contains.",
    },
    {
        "id": "G_drift_D6", "base": "G", "label": "world_drift", "fault_mode": "D6",
        "canary": CANARY["G"],
        "seed": {"log.txt": "line1\nline2\n", ".cache/log.txt": "line1\n"},
        "task": f"Append the line 'line3-{CANARY['G']}' to log.txt, then report "
                f"how many lines the file contains.",
    },
    {
        "id": "G_halluc", "base": "G", "label": "halluc", "fault_mode": "none",
        "canary": CANARY["G"],
        "seed": {"log.txt": "line1\nline2"},   # no trailing newline
        "task": f"Append the line 'line3-{CANARY['G']}' to log.txt, then report "
                f"how many lines the file contains.",
    },
]


def by_label(label: str):
    return [t for t in TASKS if t["label"] == label]