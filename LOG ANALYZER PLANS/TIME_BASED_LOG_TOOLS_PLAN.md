# Time-Based Log Tools Implementation Plan

## Overview
When diagnosing issues in distributed systems or complex applications, finding the error message is only half the battle. To understand the *state* of the system right before the crash, the diagnostic sub-agent needs to read the logs chronologically. 

To enable this, we will build two time-based log reading tools: `get_log_time_bounds` and `read_log_time_range`.

---

## 1. Tool: `get_log_time_bounds`
**Purpose:** Helps the agent understand the total chronological span of a given log file so it knows what time formats and ranges are valid.

**Parameters:**
- `log_id_or_path` (str): The ID of the log file from the `analyzer_config.json` or its absolute path.

**Execution Mechanism:**
1. **Start Time:** Open the file, read the first few non-empty lines, and use regex to extract the first valid timestamp.
2. **End Time:** Seek to the end of the file (`os.SEEK_END`), read the last few non-empty lines backward, and extract the final timestamp.
3. **Robustness:** The regex should flexibly match common formats like `[YYYY-MM-DD HH:MM:SS]` or `YYYY/MM/DD HH:MM:SS`.

**Output Format:**
```json
{
  "log_file": "C:/logs/app.log",
  "start_time": "2026-06-06 08:00:00",
  "end_time": "2026-06-06 18:30:45",
  "total_duration": "10 hours, 30 minutes"
}
```

---

## 2. Tool: `read_log_time_range`
**Purpose:** Allows the agent to zoom into a specific slice of time. For example, if the agent finds an error at `14:32:05`, it can request the logs from `14:31:00` with a span of `65` seconds to see exactly what led up to the crash.

**Parameters:**
- `log_id_or_path` (str): The target log file.
- `start_time` (str): The target start time (e.g., `"2026-06-06 14:30:00"` or just `"14:30:00"`).
- `span_seconds` (int): How many seconds of logs to return after the `start_time`. (Default: 60)

**Execution Mechanism:**
1. **Parsing:** Parse `start_time` into a Python `datetime` object. 
2. **Scanning:** Iterate through the log file. Use regex to extract the timestamp from each line.
3. **Filtering:** 
   - If a line's timestamp is `< start_time`, skip it.
   - If a line's timestamp is `>= start_time` and `<= start_time + span_seconds`, append it to the results.
   - If a line has no timestamp (e.g., a multi-line stack trace), it inherits the timestamp of the line immediately preceding it.
   - If the timestamp exceeds `start_time + span_seconds`, stop reading (early exit for performance).

**Output Format:**
Returns a single string block of the raw logs from that exact time window:
```text
[2026-06-06 14:31:00] [INFO] Database connected.
[2026-06-06 14:31:15] [WARN] Connection pool reaching limit.
[2026-06-06 14:31:45] [INFO] User Hridoy attempting login...
[2026-06-06 14:32:05] [ERROR] NullReferenceException in StartAdvertising
    at DiscoveryService.StartAdvertising() in src/Network/DiscoveryService.cs:44
```

---

## 3. Integration into `/analyze`
- Both tools will be added to the sub-agent's restricted toolset.
- **The Temporal Workflow:** 
  1. The agent uses `search_logs` to find the exact error message.
  2. The agent notes the timestamp of that error.
  3. The agent uses `read_log_time_range` to pull the 60 seconds of logs *prior* to that error to see what state the application was in (e.g., memory warnings, user login events, etc.) before the crash happened.
