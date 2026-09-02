from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from coding_agent.tools import WorkspaceAccessError, WorkspaceToolbox


class WorkspaceToolboxTests(unittest.TestCase):
    def test_write_and_read_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            toolbox = WorkspaceToolbox(workspace_root)
            write_result = toolbox.write_file({"path": "sample.txt", "content": "alpha\nbeta"})
            self.assertTrue(write_result.success)

            read_result = toolbox.read_file({"path": "sample.txt", "start_line": 1, "max_lines": 10})
            self.assertTrue(read_result.success)
            self.assertIn("alpha", read_result.content)
            self.assertIn("beta", read_result.content)

    def test_rejects_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            toolbox = WorkspaceToolbox(workspace_root)
            with self.assertRaises(WorkspaceAccessError):
                toolbox.read_file({"path": "../escape.txt"})

    def test_call_converts_workspace_errors_to_tool_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            toolbox = WorkspaceToolbox(workspace_root)
            result = toolbox.call("read_file", {"path": "../escape.txt"})
            self.assertFalse(result.success)
            self.assertIn("Path escapes workspace", result.content)
            self.assertEqual(result.metadata["error_type"], "WorkspaceAccessError")

    def test_call_rejects_invalid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            toolbox = WorkspaceToolbox(workspace_root)
            result = toolbox.call("read_file", {"path": "sample.txt", "unexpected": True})
            self.assertFalse(result.success)
            self.assertEqual(result.metadata["error_type"], "SchemaValidationError")
            self.assertIn("unexpected properties", result.content)

    def test_execute_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            toolbox = WorkspaceToolbox(workspace_root)
            result = toolbox.execute_command({"command": 'python -c "print(123)"'})
            self.assertTrue(result.success)
            self.assertIn("123", result.content)

    def test_search_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            (workspace_root / "a.py").write_text("alpha\nbeta\ngamma", encoding="utf-8")
            (workspace_root / "b.md").write_text("nothing here", encoding="utf-8")
            toolbox = WorkspaceToolbox(workspace_root)
            result = toolbox.search_text({"query": "beta", "path": ".", "recursive": True})
            self.assertTrue(result.success)
            self.assertIn("a.py", result.content)
            self.assertIn("beta", result.content)

    def test_replace_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            file_path = workspace_root / "sample.py"
            file_path.write_text("value = 1\n", encoding="utf-8")
            toolbox = WorkspaceToolbox(workspace_root)
            result = toolbox.replace_text({"path": "sample.py", "old_text": "1", "new_text": "2", "count": 1})
            self.assertTrue(result.success)
            self.assertEqual(file_path.read_text(encoding="utf-8"), "value = 2\n")
            self.assertIn("Diff", result.content)
            self.assertIn("diff_preview", result.metadata)


if __name__ == "__main__":
    unittest.main()
