# Log Updating Plan

## Objective
The objective is to restructure the `liteagent` logging format so that logs are highly readable and uncluttered, removing verbose technical data and structuring it semantically.

## Requirements
1. **[CONFIG]**: At the start of the session, output the provider, settings, and config-related items.
2. **[USER PROMPT]**: Show the exact user prompt.
3. **[AGENT THINKING]**: Include any thinking/reasoning content the agent generated.
4. **[TOOL CALL]**: Log the agent's tool invocations, showing the tool name and parameters.
5. **[TOOL RESULT]**: Show the output returned by the tool.
6. **[AGENT RESPONSE]**: Show the final agent output after loop execution.
7. **[ERROR]**: All possible errors must be captured by the log. Any issue, exception, or failure-level event must be explicitly recorded with its specific name, component, and payload.
8. **[NO BIG JSON]**: No massive or raw JSON payloads should be present in the log file. It must be highly readable and uncluttered.
9. **[NO SEPARATORS]**: Do not include dash separator lines (e.g., `---------`) between log entries. Keep it clean with just empty lines.
10. **[SINGLE LINE FORMATTING]**: The tags and their associated data must be formatted as a single line (e.g., `[TOOL RESULT] Tool: grep_search Output: {"File":"..."}`). Do not spread `Tool:`, `Parameters:`, or `Output:` across multiple lines.

## Implementation Plan
1. **Target File**: `src/liteagent/core/logger.py`
2. **Function to Modify**: `_record_to_text(record: Dict[str, Any]) -> str`
3. **Changes**:
   - Parse `event_type` and `payload` to generate clean strings formatted with the required tags.
   - For `session_started`, output `[CONFIG]`.
   - For `user_input`, output `[USER PROMPT]`.
   - For `assistant_message`, determine if the content contains `reasoning`, plain `content`, or final response depending on the presence of `tool_calls`. Output `[AGENT THINKING]` and `[AGENT RESPONSE]`.
   - For `tool_execute_start`, output `[TOOL CALL]`.
   - For `tool_execute_end`, output `[TOOL RESULT]`.
   - For any error-level logs or error event types, capture them clearly with `[ERROR] (<event_name>)`.
   - Suppress other verbose, internal events to declutter the log.
