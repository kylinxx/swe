# English Interview Script

## 1. 1-Minute Version

Hi, I built a lightweight coding agent from scratch. It connects to a language model, reads and edits local files, runs commands, and keeps iterating until the task is solved.

The project is organized into four parts: the LLM client, the local tool layer, the conversation history manager, and the main execution loop. I also added a planning mode, so the agent can generate a structured JSON plan first and then execute it step by step.

For safety and reliability, I added workspace boundary checks, command timeouts, output truncation, and error reporting. In the demo, the agent can fix a buggy calculator project, rerun tests, and save a run report automatically.

## 2. 3-Minute Version

Hi, I built a coding agent from scratch as my software engineering project. My goal was to create a simplified version of tools like Claude Code or Codex: a system that can reason with an LLM, use local tools, and complete real programming tasks.

Architecturally, the project has four core layers. First, there is an OpenAI-compatible LLM client, so the agent can talk to compatible model APIs. Second, there is a local toolbox that implements file reading, file writing, directory listing, text search, text replacement, and command execution. Third, there is a conversation history manager that trims context when the conversation gets long. Fourth, there is the main agent loop, which keeps calling the model, parsing tool calls, executing tools locally, and feeding the results back into the conversation.

To make the agent more practical and easier to present, I added a planning mode. In that mode, the agent first generates a structured JSON plan with a goal, summary, steps, and notes. After that, it executes the task step by step. This makes the workflow much closer to a real coding assistant and also helps with long or complex tasks.

I also focused on reliability and safety. The agent only works inside the configured workspace, so it cannot go outside the project directory. Commands have timeouts, outputs are truncated to avoid token explosion, and every run produces a report with the plan, tool trace, event log, and final answer. If something fails, it also saves a failure report, which makes debugging and demonstration much easier.

For the demo, I used a small buggy calculator project. The agent reads the failing test, searches the codebase, patches the bug, reruns the test, and saves the run report automatically. I think this project shows the full agent loop: understanding the task, planning, tool use, execution, validation, and final reporting.

## 3. Fast Memorization Version

- “I built a lightweight coding agent from scratch.”
- “It has four layers: LLM client, tools, memory, and the main loop.”
- “I also added planning mode, workspace protection, timeouts, and run reports.”
- “The demo shows the agent fixing a buggy calculator project end to end.”
