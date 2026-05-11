from langgraph.graph import StateGraph, START, END
from functools import partial
from .nodes.planner import planner_node
from .nodes.executor import executor_node
from ..core.state import AgentState
from ..providers.base import BaseProvider

def create_graph(provider: BaseProvider):
    workflow = StateGraph(AgentState)

    # In ReAct, the 'planner' acts as the core agent
    workflow.add_node("agent", partial(planner_node, provider=provider))
    workflow.add_node("executor", executor_node)

    workflow.add_edge(START, "agent")

    def should_continue(state: AgentState):
        messages = state.get("messages", [])
        if not messages:
            return END
        
        last_msg = messages[-1]
        # If the agent wants to call tools, go to executor
        if last_msg.get("tool_calls"):
            return "executor"
        
        # If the agent has a final text answer, end the turn
        return END

    workflow.add_conditional_edges("agent", should_continue)
    
    # After tools run, always return to the agent to observe results and think
    workflow.add_edge("executor", "agent")

    return workflow.compile()
