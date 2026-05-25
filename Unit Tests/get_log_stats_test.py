import unittest
from pathlib import Path
import sys
import os

# Ensure the src directory is in the path so we can import liteagent
sys.path.insert(0, str(Path(os.path.abspath(__file__)).parent.parent / "src"))

from liteagent.tools.factory import ToolFactory

class GetLogStatsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project_dir = Path(__file__).parent.parent / "tests" / "test-project" / "CodeShareTest"
        tools = ToolFactory.create_all_tools(project_dir)
        
        cls.get_log_stats = next(t for t in tools if t.__name__ == "get_log_stats")

    def test_global_error_stats(self):
        """Test getting stats for all errors globally."""
        result = self.__class__.get_log_stats(level="ERROR")
        self.assertNotIn("No log templates found", result)
        self.assertIn("Log Statistics for module=None, level=ERROR:", result)
        self.assertIn("[ERROR]", result)
        self.assertIn("Start", result)
        self.assertIn("Program.cs", result)

    def test_module_specific_stats(self):
        """Test getting stats for a specific module."""
        result = self.__class__.get_log_stats(module="Program.cs")
        self.assertNotIn("No log templates found", result)
        self.assertIn("Log Statistics for module=Program.cs", result)
        self.assertIn("Start", result)
        self.assertIn("Program.cs", result)
        # Should include different levels since we didn't filter by level
        self.assertTrue("[WARN]" in result or "[ERROR]" in result or "[FATAL]" in result)

    def test_non_existent_module(self):
        """Test getting stats for a module that doesn't exist."""
        result = self.__class__.get_log_stats(module="GhostModuleThatDoesNotExist")
        self.assertIn("No log templates found in codebase for module=GhostModuleThatDoesNotExist", result)

    def test_filter_by_info_level(self):
        """Test getting stats specifically for INFO logs."""
        result = self.__class__.get_log_stats(level="INFO")
        self.assertNotIn("No log templates found", result)
        self.assertIn("Log Statistics for module=None, level=INFO:", result)
        self.assertIn("[INFO]", result)
        self.assertNotIn("[ERROR]", result)
        self.assertNotIn("[FATAL]", result)

    def test_filter_by_module_and_level(self):
        """Test getting stats filtering by both module and level."""
        result = self.__class__.get_log_stats(module="Program.cs", level="FATAL")
        self.assertNotIn("No log templates found", result)
        self.assertIn("Log Statistics for module=Program.cs, level=FATAL:", result)
        self.assertIn("[FATAL]", result)
        self.assertIn("bootloader\\ initialized", result)
        self.assertNotIn("[ERROR]", result)
        
if __name__ == '__main__':
    unittest.main()
