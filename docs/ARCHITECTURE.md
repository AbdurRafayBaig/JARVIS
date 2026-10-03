# JARVIS Architecture

## Request flow

```
text panel / CLI / push-to-talk / wake word
        |
        v
Agent.execute_task(goal)
  1. remember the goal            (conversation memory)
  2. build context                (recent turns, preferences, related knowledge)
  3. planner.plan(goal, context)  -> ordered TaskSteps, one tool each
  4. for each step:
       resolve {{step_N.result}} placeholders
       ask for approval if the tool is sensitive or dangerous
       run the tool, write an audit row
       on failure: planner.replan(...) replaces the rest of the plan
  5. ResponseGenerator summarises the outcome in plain language
  6. persist the task and its steps (task history)
```

## Planners

`HybridPlanner` is the default and tries, in order:

1. **Intent router** (`agent/intent_router.py`): pattern rules for direct
   computer commands. It splits a goal into clauses and answers only if every
   clause is recognised, so a partly understood goal is never partly executed.
   No model is called; replies are composed by `agent/local_summary.py`.
2. **`LLMPlanner`**: sends the goal, context and tool schemas to the LLM and
   parses a JSON plan.
3. **Fallback**: if the LLM call fails, a plain reply that the model is needed.
   The LLM is then skipped for five minutes so later requests fail fast.

To teach the router a new command, add a rule method to `IntentRouter` and a
row to `SINGLE_COMMANDS` in `tests/unit/test_intent_router.py`.

## Passing data between steps

The plan is written before anything runs, so a step refers to an earlier
result with a placeholder that is substituted at execution time:

| Placeholder | Meaning |
|-------------|---------|
| `{{step_1.result}}` / `{{step_1}}` | Result of step 1 (1-based) |
| `{{previous.result}}` | Result of the step just before |
| `{{step_2.result.url}}` | Key `url` of a dict result |

## Writing a tool

Subclass `BaseTool` (`jarvis/agent/tools.py`), implement `name`,
`description`, optionally `risk_level`, and an async `execute`. The schema the
planner sees is built from the `execute` signature and the `Args:` section of
its docstring, so document every argument. Register the tool in the module's
`register_*_tools()` function.

Risk levels: `SAFE` runs without asking, `SENSITIVE` asks when
`REQUIRE_CONFIRMATION_SENSITIVE=true`, `DANGEROUS` always asks and is blocked
entirely when `SANDBOX_MODE=true`.

## Storage

SQLite at `%APPDATA%\Jarvis\jarvis.db`:

| Table | Written by |
|-------|-----------|
| `tasks`, `task_steps` | `memory/task_store.py` after each step |
| `conversations` | `memory/conversation_memory.py`, each goal and reply |
| `audit_logs` | `security/audit.py`, each tool call and approval |
| `projects`, `preferences` | the memory tools |

Semantic entries live in `vector_entries.json` beside the database. Memory,
audit and history are inert until `init_database()` has run, which keeps unit
tests off the real database.

## Threads and the event loop

In GUI mode a single `qasync` loop drives both Qt and asyncio. Anything that
blocks runs on a worker thread and hands results back to the loop: microphone
capture, playback, Porcupine wake-word detection, Whisper inference, SAPI
speech, and the Win32 message pump for global hotkeys.
