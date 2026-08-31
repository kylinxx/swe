# English Interview Script

## 1. Short self-introduction
“Hi, I built a lightweight coding agent from scratch. It interacts with a language model, decides when to read or edit files, runs commands locally, and iterates until the coding task is done.”

## 2. Core architecture
“The project has four main parts: an OpenAI-compatible LLM client, a local toolbox, a conversation history manager, and a main execution loop. I implemented the tool execution myself instead of wrapping an existing agent framework.”

## 3. Planning mode
“To make it feel closer to a real coding assistant, I added a planning mode. The agent first produces a structured JSON plan, then executes the task step by step. That makes the workflow easier to follow and easier to present.”

## 4. Safety and reliability
“I also added workspace boundary checks, command timeouts, output truncation, and error feedback. These are important because a coding agent needs to be useful but also controlled.”

## 5. Demo behavior
“For the demo, I used a small buggy calculator project. The agent reads the failing test, finds the bug, patches the code, reruns the tests, and saves a run report automatically.”

## 6. If the interviewer asks why this project matters
“This project demonstrates the full agent loop: understanding the task, planning, tool use, execution, validation, and final reporting. I think that is the most important foundation for building practical coding assistants.”

## 7. If asked about my contribution
“I designed the architecture, implemented the tool layer and planning workflow, wrote the error handling and reporting logic, and created the demo workspace and presentation materials.”

