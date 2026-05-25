import unittest
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(os.path.abspath(__file__)).parent.parent / "src"))

from liteagent.insight.agent import setup_insight_tools

class TraceLogToCodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project_dir = Path(__file__).parent.parent / "tests" / "test-project" / "CodeShareTest"
        tools = setup_insight_tools(project_dir)
        cls.trace_log_to_code = tools[4]
        # Hack to access graph_store for debugging
        cls.project_dir = project_dir

    def test_trace_exact_error_log(self):
        log_line = "[2026-05-24T18:00:01Z] [ERROR] Connection reset by peer in DatabaseService"
        result = self.__class__.trace_log_to_code(log_line)
        self.assertIn("Log successfully traced!", result)
        self.assertIn("File: ", result)
        self.assertIn("Program.cs", result)
        self.assertIn("Method: Start", result)
        self.assertIn("Source Code:", result)

    def test_trace_dynamic_warn_log(self):
        log_line = "[2026-05-24T18:05:00Z] [WARN] Background sync delayed due to high latency"
        result = self.__class__.trace_log_to_code(log_line)
        self.assertIn("Log successfully traced!", result)
        self.assertIn("Method: Start", result)
        
    def test_trace_third_party_log(self):
        log_line = "[INFO] Microsoft.Hosting.Lifetime: Application started. Press Ctrl+C to shut down."
        result = self.__class__.trace_log_to_code(log_line)
        self.assertIn("This log does not match any extracted templates", result)
        self.assertIn("third-party dependency", result)

if __name__ == '__main__':
    unittest.main()
