import unittest
import sys
import os
import json
from pathlib import Path

# Ensure the src directory is in the path so we can import liteagent
sys.path.insert(0, str(Path(os.path.abspath(__file__)).parent.parent / "src"))

from liteagent.tools.factory import ToolFactory

class TraceCallsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project_dir = Path(__file__).parent.parent / "tests" / "test-project" / "CodeShareTest"
        tools = ToolFactory.create_all_tools(project_dir)
        cls.trace_calls = next(t for t in tools if t.__name__ == "trace_calls")  # Index 1 is trace_calls

    def test_trace_callers_of_validate_token(self):
        """Test tracing who calls ValidateToken (should trace up to ProcessNextBatch and Main)"""
        result_json = self.__class__.trace_calls("ValidateToken", direction="callers", depth=3)
        result = json.loads(result_json)
        
        self.assertEqual(result["symbol"], "ValidateToken")
        self.assertIn("ProcessNextBatch", result["callers"])
        
    def test_trace_callees_of_process_next_batch(self):
        """Test tracing what ProcessNextBatch calls (should include ValidateToken and SaveData)"""
        result_json = self.__class__.trace_calls("ProcessNextBatch", direction="callees", depth=1)
        result = json.loads(result_json)
        
        self.assertEqual(result["symbol"], "ProcessNextBatch")
        self.assertIn("ValidateToken", result["callees"])
        self.assertIn("SaveData", result["callees"])

if __name__ == '__main__':
    unittest.main()
