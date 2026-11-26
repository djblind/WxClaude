# The engine "Agent SDK"

**Status: built and tried once with the real API (2026-11-25, `claude-haiku-5-5`, a Team plan): the
answer came, paid by the API credits of the plan.**

Tried through `ClaudeRunner` with the claude program of the user (2.1.317): a `Bash` command, a
`Write` that asked for the permission (allowed), and a second message that resumed the session, for
less than one cent in all.

## Why

The Max, Ultra and Team plans give API credits every month (a Team plan: 20 USD per standard seat,
100 USD per premium seat, pooled, at most 500 USD; the discounted plans for non-profits get the
same). Anthropic's page "API credits for Max, Ultra, and Team plans" lists what they pay for: the
Claude API, the Managed Agents, the **Claude Agent SDK** and the Playground of the console; **not
Claude Code** (a Claude Code session on such an organization is answered "Credit balance too low")
and not the extra usage of the apps. Once the quota of the plan is reached, a message sent through
the SDK can still be answered, with those credits.

WxClaude does not pretend to be the SDK (for example by setting `CLAUDE_CODE_ENTRYPOINT` for the CLI
it starts itself): that would go around the rule of Anthropic. A provider whose engine is the Agent
SDK really goes through the official package `claude-agent-sdk`, as an application built on it, and
names itself to it (`client_app`, `WxClaude/<version>`).

## What it is in WxClaude

A field `engine` of the provider (`providers.md`): `cli` (Claude Code, started by WxClaude, the
default and the value of a file from before the field) or `agent_sdk`. The form of the provider has
the list *Engine* after the address. Such a provider needs a key saved by WxClaude (a key of the API,
made on platform.claude.com) and its address is `https://api.anthropic.com`; its models are the full
names (`claude-haiku-5-5`...). Everything else is what any provider has: it is chosen in an agent, a
conversation switches between Claude Code and the SDK and keeps one session (the same session files,
the same `CLAUDE_CONFIG_DIR`).

## How a message is sent (`core/claude/sdk_run.py`)

`ClaudeRunner.start` sends a request whose provider uses the SDK to `SdkRun` instead of starting
`claude -p`; one message at a time, whatever the engine. `SdkRun` makes the options of the SDK from
the request, the same as `build_arguments` gives Claude Code:

| Claude Code | Agent SDK |
|---|---|
| (the system prompt of Claude Code) | `system_prompt` preset `claude_code`: without it the SDK sends an empty system prompt |
| `--model`, `--effort` (if the provider takes it), `--permission-mode`, `--max-turns` | `model`, `effort`, `permission_mode`, `max_turns` |
| `--session-id`, `--resume`, `--fork-session`, `--name` | `session_id`, `resume`, `fork_session`, `extra_args` `name` |
| `--settings` (address, aliases, variables, restricted rules) | `settings`, the same JSON (the permission channel adds nothing: the SDK asks with its own) |
| `--setting-sources user` (restricted folder) | `setting_sources ["user"]`; otherwise not given, so every source, as for Claude Code |
| the key as `ANTHROPIC_AUTH_TOKEN` in the environment | the key as `ANTHROPIC_API_KEY` (the API wants `x-api-key`) in `env` |
| the claude program found (`find_claude`) | `cli_path`, the same program; the SDK's own copy only when the command is not one program (npm through node) |

The SDK adds its `env` to the environment of WxClaude instead of replacing it, so the variables that
choose a provider and that WxClaude leaves out for the others (`ANTHROPIC_*`, `CLAUDE_CODE_USE_*`) are
given empty (`launch.blanked_variables`). Only what the launch changes is given: the
SDK names the caller itself (`CLAUDE_CODE_ENTRYPOINT=sdk-py`) and that name must stay. Measured on
2026-11-25: WxClaude started from the Claude application inherits `CLAUDE_CODE_ENTRYPOINT=claude-desktop`;
given back to the SDK with the rest of the environment, it made the API take each message for one of
Claude Code and answer "Credit balance is too low", with the same key that worked otherwise. The name
is therefore never in what WxClaude gives (`sdk_run._changed_variables`). The transmission *Relayed* does not apply: the relay gives
the key as a bearer token, which the API refuses, so such a provider goes *Masked*.

The SDK is asynchronous. Each message has a thread that runs an event loop (`asyncio.run`). The
messages of the SDK are written back as the `stream-json` objects they came from
(`core/claude/sdk_messages.py`) and go through the parser of the CLI
(`stream.parse_stream_entry`): the events, the progress, the announcements and the conversation are
the ones of Claude Code. A permission question of the SDK (`can_use_tool`) becomes a
`PermissionRequest`; it waits in the loop for `SdkRun.answer`, called by the interface thread with
the same body as for the CLI. *Interrupt* cancels the message, which closes the CLI; the run always
ends with `TurnEnded`. A failure of the SDK (the program cannot start, the CLI stops) is a diagnostic
of `TurnEnded` with the exit code 1.

## Spending

An API key cannot ask for the balance of the credits (only an admin key of the organization could
read the costs, and it opens the whole organization). So WxClaude counts it itself: the cost of each
message of an Agent SDK provider (the `total_cost_usd` of the result minus the total before, as for
the statistics, at list price) is added to `credits.json` beside the settings, by month (`YYYY-MM`,
local time) and provider (`core/config/credit_ledger.py`, through `StatsRecorder`). The file is read
again before each addition, so two windows do not erase each other. The dialog *Usage gauge* shows,
for each Agent SDK provider, what it spent this month, then says that the balance is on the console
(platform.claude.com, Billing). A message whose cost is not known (the total of the session before it
was not known) is not counted; the credits of the plan are renewed by billing period, which may not
be the calendar month.

## Packaging

`claude-agent-sdk` is a dependency. It carries its own claude program (about 400 MB), which the
packaged application leaves out (`packaging/WxClaude.spec`): the SDK is given the user's own.
The rename of a conversation and the gauges stay Claude Code's (`/rename`, `/usage`).

## Not done

- No balance of the credits: the console of Anthropic has no API for it with a key of the API; only
  what WxClaude spent is shown ("Spending").
- "Credit balance too low" is shown as the CLI gives it, not as an announcement of its own.
