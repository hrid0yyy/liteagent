from typing import TypedDict, Annotated, List, Dict, Any
from operator import add

class AppState:
    def __init__(self):
        self.auto_mode = False
        self.read_tracker: Dict[str, Dict[str, Any]] = {}

app_state = AppState()

class AgentState(TypedDict):
    # The history of messages in the conversation
    messages: Annotated[List[dict], add]
    # The current plan being executed
    plan: str
    # Results from tool executions
    tool_outputs: Annotated[List[dict], add]
    # Any errors encountered during execution
    errors: Annotated[List[str], add]
    # Whether the task is completed
    is_complete: bool
