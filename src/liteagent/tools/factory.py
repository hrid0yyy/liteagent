from pathlib import Path
from .providers import ToolProviderFactory
from .get_workspace_info_tool import create_get_workspace_info_tool
from .search_in_files_tool import create_search_in_files_tool
from .list_files_tool import create_list_files_tool
from .read_file_tool import create_read_file_tool
from .read_log_lineRange_tool import create_read_log_lineRange_tool
from .search_logs_tool import create_search_logs_tool
from .extract_log_patterns_tool import create_extract_log_patterns_tool

class ToolFactory:
    @staticmethod
    def create_all_tools(project_dir: Path, include_insight: bool = True):
        providers = ToolProviderFactory(project_dir, include_insight)
        tools = [
            create_get_workspace_info_tool(providers),
            create_search_in_files_tool(providers),
            create_list_files_tool(providers),
            create_read_file_tool(providers),
            create_read_log_lineRange_tool(providers),
        ]
        if include_insight:
            tools.extend([
                create_search_code_tool(providers),
                create_search_logs_tool(providers),
                create_extract_log_patterns_tool(providers),
            ])
        return tools
