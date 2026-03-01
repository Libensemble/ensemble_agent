"""Debug logging for agent message history.

Writes to a single debug_log.txt that captures system prompt, tool schemas,
and full message history after each agent invocation.

Activated via --debug flag or AGENT_DEBUG=1 env var.
"""

import time
from pathlib import Path


class DebugLogger:
    """Appends agent conversation details to debug_log.txt."""

    def __init__(self, log_path, model=""):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "w") as f:
            f.write(f"Debug log started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Model: {model}\n\n")

    def log_system_prompt(self, prompt):
        with open(self.log_path, "a") as f:
            f.write("SYSTEM PROMPT\n" + "=" * 80 + "\n")
            f.write(prompt + "\n\n")

    def log_tool_schemas(self, tools):
        with open(self.log_path, "a") as f:
            f.write("TOOL SCHEMAS\n" + "=" * 80 + "\n")
            for t in tools:
                f.write(f"\n{t.name}: {t.description}\n")
                if t.args_schema:
                    if hasattr(t.args_schema, "model_json_schema"):
                        f.write(f"  inputSchema: {t.args_schema.model_json_schema()}\n")
                    elif isinstance(t.args_schema, dict):
                        f.write(f"  inputSchema: {t.args_schema}\n")
            f.write("\n")

    def dump_messages(self, messages, label=""):
        with open(self.log_path, "a") as f:
            f.write(f"\n{'=' * 80}\n")
            if label:
                f.write(f"  {label}\n{'=' * 80}\n")
            for msg in messages:
                role = type(msg).__name__
                f.write(f"\n--- {role} ---\n")
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    f.write("[Tool calls]\n")
                    for tc in msg.tool_calls:
                        f.write(f"  {tc.get('name', '?')}({tc.get('args', {})})\n")
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                if content:
                    if len(content) > 2000:
                        f.write(
                            content[:1000]
                            + f"\n... [{len(content)} chars total] ...\n"
                            + content[-500:]
                            + "\n"
                        )
                    else:
                        f.write(content + "\n")
            f.write(f"\n{'=' * 80}\n\n")
