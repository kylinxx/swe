# Demo Script

## One-Sentence Goal

Show that the agent can understand a coding task, plan, use local tools, fix a bug, rerun tests, and save a run report.

## Suggested Flow

1. Open the repository and briefly explain the architecture.
2. Start the agent on `demo_workspace/mini_buggy_app`.
3. Show the planning step.
4. Show the tool loop: read, search, edit, execute.
5. Show the test passing.
6. Open the generated report in `.coding-agent/runs/`.

## Talking Points

- The agent is built from scratch.
- It does not depend on an agent framework.
- The tool execution happens locally in the workspace.
- The report makes the run easy to review and defend during the interview.
