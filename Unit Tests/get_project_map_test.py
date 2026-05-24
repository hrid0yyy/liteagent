import unittest
import sys
import os
from pathlib import Path

# Ensure the src directory is in the path so we can import liteagent
sys.path.insert(0, str(Path(os.path.abspath(__file__)).parent.parent / "src"))

from liteagent.insight.agent import setup_insight_tools

class GetProjectMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project_dir = Path(__file__).parent.parent / "tests" / "test-project" / "CodeShareTest"
        tools = setup_insight_tools(project_dir)
        cls.get_project_map = tools[2]  # Index 2 is get_project_map

    def test_get_root_project_map(self):
        """Test retrieving the project map at the root directory."""
        result = self.__class__.get_project_map(".")
        
        self.assertNotIn("Error", result)
        self.assertIn("[FILE] Program.cs", result)
        self.assertIn("[FILE] CodeShareTest.csproj", result)
        self.assertIn("[DIR ]", result) # Should contain bin or obj directories if built, but at least Program.cs exists

    def test_get_invalid_directory(self):
        """Test retrieving map for a non-existent directory."""
        result = self.__class__.get_project_map("FakeDirectoryThatDoesNotExist")
        self.assertIn("Path does not exist", result)

if __name__ == '__main__':
    unittest.main()
