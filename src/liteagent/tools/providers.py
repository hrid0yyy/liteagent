from pathlib import Path
from ..core.container import get_container
from ..insight.providers import InsightProviders

class ToolProviderFactory:
    def __init__(self, project_dir: Path, include_insight: bool = True):
        self.project_dir = project_dir
        self.container = get_container()
        self.insight = InsightProviders(project_dir) if include_insight else None
