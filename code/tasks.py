"""
Labelled task set for the fs testbed.

Matched-pairs design: each BASE task appears under several conditions that
share the same instruction and the same seed wherever possible. Only the
injected fault differs. This controls for task difficulty, so a classifier
cannot cheat by reading surface features of the task itself.

Ground-truth label semantics:
  clean       - no fault injected
  world_drift - server behaviour contradicts its own unchanged description
  halluc      - server is correct and correctly documented; the agent's
                belief about the effect of its own action is what goes wrong

Note: an injected fault is NOT the same as an observed discrepancy. If the
agent happens to produce the right world state anyway, that trial carries no
attribution signal and is scored separately, not as a miss.
"""

TASKS = [
    # ---------------------------------------------------------------- base A
    # Overwrite semantics. The doc says write_file replaces contents.
    {
        "id": "A_clean",
        "base": "A",
        "label": "clean",
        "fault_mode": "none",
        "seed": {"report.txt": "Q1 revenue: 120\nQ2 revenue: 145\n"},
        "task": "Replace the entire contents of report.txt with the single "
                "line 'Q3 revenue: 160'.",
    },
    {
        "id": "A_drift_D1",
        "base": "A",
        "label": "world_drift",
        "fault_mode": "D1",          # write_file silently appends
        "seed": {"report.txt": "Q1 revenue: 120\nQ2 revenue: 145\n"},
        "task": "Replace the entire contents of report.txt with the single "
                "line 'Q3 revenue: 160'.",
    },
    {
        "id": "A_halluc",
        "base": "A",
        "label": "halluc",
        "fault_mode": "none",        # server behaves exactly as documented
        "seed": {"report.txt": "Q1 revenue: 120\nQ2 revenue: 145\n"},
        # phrased to invite the belief that writing is additive
        "task": "Add the line 'Q3 revenue: 160' to report.txt using write_file, "
                "then confirm the file holds the full year to date.",
    },

    # ---------------------------------------------------------------- base B
    # Deletion. The doc says delete_file permanently removes.
    {
        "id": "B_clean",
        "base": "B",
        "label": "clean",
        "fault_mode": "none",
        "seed": {"old.txt": "stale\n", "keep.txt": "current\n"},
        "task": "Delete old.txt, then list the directory and report how many "
                "files remain.",
    },
    {
        "id": "B_drift_D5",
        "base": "B",
        "label": "world_drift",
        "fault_mode": "D5",          # soft delete into .trash
        "seed": {"old.txt": "stale\n", "keep.txt": "current\n"},
        "task": "Delete old.txt, then list the directory and report how many "
                "files remain.",
    },
    {
        "id": "B_halluc",
        "base": "B",
        "label": "halluc",
        "fault_mode": "none",
        # a dotfile exists; list_dir documents that dotfiles are hidden, so a
        # belief about "how many files remain" formed from list_dir is wrong
        "seed": {"old.txt": "stale\n", "keep.txt": "current\n",
                 ".config": "hidden\n"},
        "task": "Delete old.txt, then list the directory and report how many "
                "files remain in total.",
    },

    # ---------------------------------------------------------------- base C
    # Where a written file actually lands.
    {
        "id": "C_clean",
        "base": "C",
        "label": "clean",
        "fault_mode": "none",
        "seed": {},
        "task": "Create notes/summary.txt containing 'draft one', then read it "
                "back to confirm it is where you expect.",
    },
    {
        "id": "C_drift_D4",
        "base": "C",
        "label": "world_drift",
        "fault_mode": "D4",          # silently prefixed with drafts/
        "seed": {},
        "task": "Create notes/summary.txt containing 'draft one', then read it "
                "back to confirm it is where you expect.",
    },

    # ---------------------------------------------------------------- base D
    # Undocumented precondition appears.
    {
        "id": "D_clean",
        "base": "D",
        "label": "clean",
        "fault_mode": "none",
        "seed": {"log.txt": "boot ok\n"},
        "task": "Write 'shutdown ok' into log.txt, then verify the write "
                "succeeded by reading the file.",
    },
    {
        "id": "D_drift_D2",
        "base": "D",
        "label": "world_drift",
        "fault_mode": "D2",          # write_file now needs acquire_lock first
        "seed": {"log.txt": "boot ok\n"},
        "task": "Write 'shutdown ok' into log.txt, then verify the write "
                "succeeded by reading the file.",
    },

    # ---------------------------------------------------------------- base E
    # Return-format change vs. a counting belief. Must act on a subdirectory,
    # not top-level, or the D3 path-prefix drift has nothing to attach to.
    {
        "id": "E_clean",
        "base": "E",
        "label": "clean",
        "fault_mode": "none",
        "seed": {"docs/a.txt": "1\n", "docs/b.txt": "2\n", "docs/note.md": "x\n"},
        "task": "List the contents of the docs directory and write the names "
                "you found, one per line, into docs/index.txt.",
    },
    {
        "id": "E_drift_D3",
        "base": "E",
        "label": "world_drift",
        "fault_mode": "D3",          # list_dir returns full paths, doc says names
        "seed": {"docs/a.txt": "1\n", "docs/b.txt": "2\n", "docs/note.md": "x\n"},
        "task": "List the contents of the docs directory and write the names "
                "you found, one per line, into docs/index.txt.",
    },
    {
        "id": "E_halluc",
        "base": "E",
        "label": "halluc",
        "fault_mode": "none",
        # append_file is documented and available; the task wording invites
        # reaching for write_file with an additive belief
        "seed": {"a.txt": "1\n", "b.txt": "2\n", "index.txt": "existing\n"},
        "task": "Record each top-level entry into index.txt, keeping whatever "
                "index.txt already contains.",
    },
    # ---------------------------------------------------------------- base F
    # Long-horizon chain with a data dependency: what the agent reads in step 1
    # decides what it writes in step 2. This is the only base where an early
    # wrong input propagates, so it is the one that makes early-detection-step
    # measurable at all.
    #
    # Note on matched pairs: .cache/config.txt is seeded in ALL three
    # conditions. Only D6 ever reads it, so the seeds stay identical and the
    # condition cannot be inferred from the starting world.
    {
        "id": "F_clean",
        "base": "F",
        "label": "clean",
        "fault_mode": "none",
        "seed": {
            "config.txt": "target: alpha.txt\nmode: replace\n",
            "alpha.txt": "old alpha\n",
            "beta.txt": "old beta\n",
            ".cache/config.txt": "target: beta.txt\nmode: replace\n",
        },
        "task": "Read config.txt to find which file is the current target, "
                "write 'PROCESSED' into that target file, then read the target "
                "back and confirm what it now contains.",
    },
    {
        "id": "F_drift_D6",
        "base": "F",
        "label": "world_drift",
        "fault_mode": "D6",          # read_file silently serves a stale cache
        "seed": {
            "config.txt": "target: alpha.txt\nmode: replace\n",
            "alpha.txt": "old alpha\n",
            "beta.txt": "old beta\n",
            ".cache/config.txt": "target: beta.txt\nmode: replace\n",
        },
        "task": "Read config.txt to find which file is the current target, "
                "write 'PROCESSED' into that target file, then read the target "
                "back and confirm what it now contains.",
    },
    {
        "id": "F_halluc",
        "base": "F",
        "label": "halluc",
        "fault_mode": "none",        # server correct and correctly documented
        # config asks for append mode; append_file exists and is documented.
        # Reaching for write_file here is a belief error about effect, not a
        # tool fault.
        "seed": {
            "config.txt": "target: alpha.txt\nmode: append\n",
            "alpha.txt": "old alpha\n",
            "beta.txt": "old beta\n",
            ".cache/config.txt": "target: beta.txt\nmode: append\n",
        },
        "task": "Read config.txt, then update the target file according to the "
                "mode given there by adding the line 'PROCESSED'. Confirm the "
                "target file afterwards.",
    },

    # ---------------------------------------------------------------- base G
    # Accumulated state under repetition. Forces the agent to hold a belief
    # about a COUNT, which is the belief most easily contradicted by the true
    # world state. This is the base that exercises Layer 4's axis B, since a
    # wrong count leaves the agent holding two beliefs that cannot both hold.
    {
        "id": "G_clean",
        "base": "G",
        "label": "clean",
        "fault_mode": "none",
        "seed": {"log.txt": "line1\nline2\n"},
        "task": "Append the line 'line3' to log.txt, then report how many "
                "lines the file contains.",
    },
    {
        "id": "G_drift_D7",
        "base": "G",
        "label": "world_drift",
        "fault_mode": "D7",          # append_file silently writes twice
        "seed": {"log.txt": "line1\nline2\n"},
        "task": "Append the line 'line3' to log.txt, then report how many "
                "lines the file contains.",
    },
    {
        "id": "G_halluc",
        "base": "G",
        "label": "halluc",
        "fault_mode": "none",
        # log.txt has NO trailing newline. append_file concatenates exactly as
        # documented, so 'line3' fuses onto 'line2'. The tool is blameless; the
        # agent's belief that appending yields a separate line is what fails.
        "seed": {"log.txt": "line1\nline2"},
        "task": "Append the line 'line3' to log.txt, then report how many "
                "lines the file contains.",
    },
]


def by_label(label: str):
    return [t for t in TASKS if t["label"] == label]