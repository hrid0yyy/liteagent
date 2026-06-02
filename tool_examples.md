# LiteAgent Diagnostic Tools - Sample Usage Guide
This document provides sample inputs and expected outputs for the 5 core diagnostic tools, tested against the `CodeShareTest` test project.

## 1. `search_code`
Searches the codebase for specific functionality, concepts, or logic.

**Example 1:**
- **Input:** `query="ValidateToken logic"`, `top_k=3`
- **Expected Output:** Returns a JSON structure containing the `AuthService` class, the `ValidateToken` method, and the C# source code snippet implementing it.

**Example 2:**
- **Input:** `query="net8.0"`, `top_k=3`
- **Expected Output:** Returns a match inside `CodeShareTest.csproj` highlighting the `<TargetFramework>net8.0</TargetFramework>` node.

---

## 2. `search_logs`
Searches through application log files for errors, keywords, or patterns.

**Example 1:**
- **Input:** `query="Connection reset"`, `is_plain=True`
- **Expected Output:** Returns the exact log lines such as `[2026-05-24T18:00:01Z] [ERROR] Connection reset by peer in DatabaseService` along with surrounding context.

**Example 2:**
- **Input:** `query="bootloader initialized"`, `is_plain=True`
- **Expected Output:** Returns the critical startup log `[FATAL] Critical system bootloader initialized (AppVersion v1.0.0)`.
