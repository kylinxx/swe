# Task

Fix `safe_join()` so that path traversal is blocked and normal paths still work.

## Rules

- Return an absolute path inside the base directory for valid inputs.
- Raise `ValueError` when the candidate escapes the base directory.
