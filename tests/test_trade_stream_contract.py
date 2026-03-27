import ast
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _parse_module(relative_path: str) -> ast.Module:
    source = (BACKEND_ROOT / relative_path).read_text()
    return ast.parse(source, filename=relative_path)


class TradeStreamContractTests(unittest.TestCase):
    def test_sessions_exposes_user_lookup_for_active_playbooks(self) -> None:
        tree = _parse_module("app/sessions.py")
        function_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        self.assertIn("get_user_for_playbook", function_names)

    def test_alpaca_trade_stream_imports_user_lookup_helper(self) -> None:
        tree = _parse_module("app/alpaca_ws.py")

        imported_names = set()
        referenced_names = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "app.sessions":
                imported_names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Name):
                referenced_names.add(node.id)

        self.assertIn("get_user_for_playbook", imported_names)
        self.assertIn("get_user_for_playbook", referenced_names)


if __name__ == "__main__":
    unittest.main()
