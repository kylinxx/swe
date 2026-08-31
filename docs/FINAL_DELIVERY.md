# Final Delivery Kit

## 1. English Interview Script — 1 Minute

“Hi, I built a lightweight coding agent from scratch. It talks to a language model, reads and edits local files, runs commands, and keeps iterating until the task is done.

The project has four main parts: an OpenAI-compatible LLM client, a local tool layer, a conversation history manager, and a main execution loop. I also added a planning mode, so the agent can first produce a structured JSON plan and then execute step by step.

For safety and reliability, I added workspace boundary checks, command timeouts, output truncation, and error reporting. For the demo, I used a small buggy calculator project, and the agent can find the bug, patch the code, rerun tests, and save a run report automatically.”

## 2. English Interview Script — 3 Minutes

“Hi, I built a coding agent from scratch as my software engineering project. The goal was to create a simplified version of tools like Claude Code or Codex: something that can reason with an LLM, use local tools, and complete real programming tasks.

Architecturally, the project is split into four core layers. First, there is an OpenAI-compatible LLM client, so the agent can talk to any compatible model API. Second, there is a local toolbox that implements file reading, file writing, directory listing, text search, text replacement, and command execution. Third, there is a conversation history manager that trims context when the conversation gets long. Fourth, there is the main agent loop, which keeps calling the model, parsing tool calls, executing tools locally, and feeding the results back into the conversation.

To make the agent more practical and easier to present, I added a planning mode. In that mode, the agent first generates a structured JSON plan with a goal, summary, steps, and notes. After that, it executes the task step by step. This makes the workflow much closer to a real coding assistant and it also helps with long or complex tasks.

I also focused on reliability and safety. The agent only works inside the configured workspace, so it cannot go outside the project directory. Commands have timeouts, outputs are truncated to avoid token explosion, and every run produces a report with the plan, tool trace, event log, and final answer. If something fails, it also saves a failure report, which makes debugging and demonstration much easier.

For the demo, I used a small buggy calculator project. The agent reads the failing test, searches the codebase, patches the bug, reruns the test, and saves the run report automatically. I think this project shows the full agent loop: understanding the task, planning, tool use, execution, validation, and final reporting. That is the core capability I wanted to demonstrate.”

## 3. Final Submission Checklist

- Public Git repository created after the assignment was released.
- Full commit history preserved, with no history rewrite.
- `README.txt` contains the repository URL, run instructions, and feature summary.
- `demo_workspace/mini_buggy_app` is ready for the video demo.
- `docs/VIDEO_SCRIPT_ZH.md` used as the recording outline.
- `docs/INTERVIEW_SCRIPT_EN.md` or this file used for the interview explanation.
- Tests pass locally: `python -m unittest discover -s tests`.
- No secrets committed in the repository, README, or video.

## 4. What to Show in the Video

1. Show the repository structure and briefly explain the architecture.
2. Run the agent on `demo_workspace/mini_buggy_app`.
3. Show planning mode first, then the tool-based execution loop.
4. Show it fixing the bug and rerunning tests.
5. Show the generated run report in `.coding-agent/runs/`.
6. End with a short summary of the project’s design choices.

## 5. Recording Tips

- Keep the demo under 2 minutes.
- Speed up boring command output if needed.
- Do not show API keys or `.env` contents.
- Use a stable demo task that finishes quickly.
- If the model is slow, record a shorter “happy path” demo first, then splice the best parts.

## 6. GitHub Push Guide

If the repository has no remote yet:

1. Create a new public repository on GitHub.
2. Copy the repository URL.
3. Add the remote:

```bash
git remote add origin https://github.com/<your-account>/<your-repo>.git
```

4. Push the current branch:

```bash
git push -u origin master
```

If you rename the branch to `main`, push with:

```bash
git branch -M main
git push -u origin main
```

If you want me to push for you, send me the GitHub repository URL first.  
Then I can stage the final files, commit them, and push the branch.

## 7. Files Worth Highlighting

- `coding_agent/agent.py` — main loop, planning mode, hooks, and artifact writing.
- `coding_agent/tools.py` — local tool execution and workspace protection.
- `coding_agent/artifacts.py` — session reports and run logs.
- `coding_agent/cli.py` — CLI entry and user-facing options.
- `demo_workspace/mini_buggy_app/` — the recording demo target.

