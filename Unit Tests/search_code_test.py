import unittest
from pathlib import Path
import sys
import os

# Ensure the src directory is in the path so we can import liteagent
sys.path.insert(0, str(Path(os.path.abspath(__file__)).parent.parent / "src"))

from liteagent.tools.factory import ToolFactory

class SearchCodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # We use the CodeShareTest project as the test project
        project_dir = Path(__file__).parent.parent / "tests" / "test-project" / "CodeShareTest"
        
        # Initialize tools
        tools = ToolFactory.create_all_tools(project_dir)
        
        cls.search_code = next(t for t in tools if t.__name__ == "search_code")

    def test_search_for_validate_token(self):
        """Test if search_code can find the ValidateToken logic."""
        result = self.__class__.search_code("ValidateToken logic")
        
        # Ensure it didn't fail to find code
        self.assertNotIn("No code found matching", result)
        
        # Ensure the correct class and method are present in the response
        self.assertIn("AuthService", result)
        self.assertIn("ValidateToken", result)

    def test_search_for_log_spammer(self):
        """Test if search_code can find how logs are spammed."""
        result = self.__class__.search_code("how are logs being spammed")
        self.assertNotIn("No code found matching", result)
        self.assertIn("LogSpammer", result)

    def test_search_for_csproj(self):
        """Test if search_code can find the .csproj file contents."""
        result = self.__class__.search_code("net8.0")
        
        # Ensure it didn't fail to find code
        self.assertNotIn("No code found matching", result)
        
        # Ensure the correct file and contents are present in the response
        self.assertIn("CodeShareTest.csproj", result)
        self.assertIn("<TargetFramework>net8.0</TargetFramework>", result)

if __name__ == '__main__':
    unittest.main()
