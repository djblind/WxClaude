"""The subagents WxClaude gives Claude with every message (``docs/interface.md``, "Subagents of
WxClaude"): cheaper models for the work that does not need the model of the conversation, so that
the quota lasts longer without a loss of quality. The main conversation decides and checks; the
``lecteur`` (Haiku) reads and searches and gives back a short summary, so that big files never
enter the conversation; the ``executant`` (Sonnet) does a task that is well defined and repetitive.

They go to the CLI with ``--agents`` (a JSON object, checked with CLI 2.1.321) and to the Agent
SDK with ``ClaudeAgentOptions.agents``. A subagent of the same name in the project or the user
folder of Claude Code is the one the user wrote: the names are chosen not to meet the usual ones.
"""

import json

SUBAGENTS: dict[str, dict[str, object]] = {
    "lecteur": {
        "description": (
            "Reads and searches for the main conversation without changing anything: big files, "
            "logs, many files of a project, the answer to a precise question about the code or "
            "the documents. Use it instead of reading a big file or searching several times "
            "yourself; give it the precise question and the folders to look in."
        ),
        "prompt": (
            "You read and search for the main conversation. You change NOTHING: no writing, no "
            "deletion, no program started except commands that only read. Look only where you "
            "are told; find the right place first (Grep, Glob), then read only that part of a "
            "big file. Answer short and exact, in the language of the request: what answers the "
            "question, with the paths and line numbers that help. If you are not sure, say so; "
            "never invent."
        ),
        "tools": ["Read", "Grep", "Glob", "Bash"],
        "model": "haiku",
    },
    "executant": {
        "description": (
            "Does a task that is well defined and needs no decision of the main conversation: the "
            "same change in many files, extracting or converting data, translating or formatting "
            "text by given rules, a long series of checks. Give it complete instructions (files, "
            "rules, what done looks like); several can run at the same time on separate files."
        ),
        "prompt": (
            "You do one well-defined task for the main conversation, exactly as asked, and nothing "
            "else. Read the instructions and the files they name before you start. Do not touch "
            "files the task does not name. Check your work as the instructions say. When you are "
            "done, answer in a few lines, in the language of the request: what you did, the "
            "result of the checks, and any doubt."
        ),
        "model": "sonnet",
    },
}


def subagents_argument(subagents: dict[str, dict[str, object]]) -> list[str]:
    """The arguments that give ``subagents`` to the CLI (none when there are none)."""
    if not subagents:
        return []
    return ["--agents", json.dumps(subagents, ensure_ascii=False)]
