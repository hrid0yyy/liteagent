import unittest
from pathlib import Path
import sys
import os

# Ensure the src directory is in the path so we can import liteagent
sys.path.insert(0, str(Path(os.path.abspath(__file__)).parent.parent / "src"))

from liteagent.tools.factory import ToolFactory

class SearchLogsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project_dir = Path(__file__).parent.parent / "tests" / "test-project" / "CodeShareTest"
        tools = ToolFactory.create_all_tools(project_dir)
        
        cls.search_logs = next(t for t in tools if t.__name__ == "search_logs")

    def test_search_for_connection_reset(self):
        """Test if search_logs can find the 'Connection reset' errors in the app.log file."""
        result = self.__class__.search_logs("Connection reset", is_plain=True)
        self.assertNotIn("No logs found matching query", result)
        self.assertIn("Connection reset by peer in DatabaseService", result)
        self.assertIn("[ERROR]", result)

    def test_search_for_one_time_log(self):
        """Test if search_logs can find the single fatal startup log."""
        result = self.__class__.search_logs("bootloader initialized", is_plain=True)
        self.assertNotIn("No logs found matching query", result)
        self.assertIn("Critical system bootloader initialized (AppVersion v1.0.0)", result)
        self.assertIn("[FATAL]", result)

    def test_search_for_rare_log(self):
        """Test if search_logs can find the rare background sync log."""
        result = self.__class__.search_logs("Background sync delayed", is_plain=True)
        self.assertNotIn("No logs found matching query", result)
        self.assertIn("Background sync delayed due to high latency", result)
        self.assertIn("[WARN]", result)

    def test_search_for_non_existent_log(self):
        """Test if search_logs correctly handles queries for logs that don't exist."""
        result = self.__class__.search_logs("Ghost in the machine failure", is_plain=True)
        self.assertEqual("No logs found matching query: Ghost in the machine failure", result)

if __name__ == '__main__':
    unittest.main()
