from pathlib import Path
from .providers import ToolProviderFactory
from .get_workspace_info_tool import create_get_workspace_info_tool
from .search_in_files_tool import create_search_in_files_tool
from .list_files_tool import create_list_files_tool
from .read_file_tool import create_read_file_tool
from .read_log_lineRange_tool import create_read_log_lineRange_tool
from .write_file_tool import create_write_file_tool
from .rename_path_tool import create_rename_path_tool
from .delete_path_tool import create_delete_path_tool
from .modify_file_tool import create_modify_file_tool
from .run_shell_command_tool import create_run_shell_command_tool
from .search_code_tool import create_search_code_tool
from .search_logs_tool import create_search_logs_tool

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
            create_write_file_tool(providers),
            create_rename_path_tool(providers),
            create_delete_path_tool(providers),
            create_modify_file_tool(providers),
            create_run_shell_command_tool(providers),
        ]
        if include_insight:
            tools.extend([
                create_search_code_tool(providers),
                create_search_logs_tool(providers),
            ])
        return tools
