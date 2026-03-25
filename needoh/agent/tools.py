"""
needoh/agent/tools.py
Direct tool implementations that run locally inside the Needoh process.

Most tools are delegated to MCP servers (filesystem, Tavily, Context7, RAG).
This module handles tools that make more sense to run directly — currently
shell command execution, which needs special handling for streaming output,
working directory tracking, and safety checks.

Future tools can be added here and registered in get_local_tools().
"""

from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
from pathlib import Path


class ShellTool:
    """
    Executes shell commands in a tracked working directory.
    Used for: running tests, installing packages, compiling code, git ops.
    """

    def __init__(self, cwd: str | None = None):
        self.cwd = cwd or os.getcwd()

    async def run(self, command: str, timeout: int = 60) -> str:
        """
        Run a shell command and return combined stdout + stderr.

        Args:
            command: Shell command string (passed to bash -c)
            timeout: Max seconds to wait (default 60)

        Returns:
            Combined output string.
        """
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            output = ""
            if stdout:
                output += stdout.decode(errors="replace")
            if stderr:
                output += stderr.decode(errors="replace")
            if proc.returncode != 0:
                output += f"\n[exit code {proc.returncode}]"
            return output.strip() or "(no output)"

        except asyncio.TimeoutError:
            return f"[ERROR] Command timed out after {timeout}s: {command}"
        except Exception as exc:
            return f"[ERROR] Failed to run command: {exc}"

    def change_dir(self, path: str) -> str:
        """
        Change the working directory for subsequent commands.
        Returns a status message.
        """
        new_path = Path(self.cwd) / path
        new_path = new_path.resolve()
        if not new_path.exists():
            return f"[ERROR] Directory not found: {new_path}"
        if not new_path.is_dir():
            return f"[ERROR] Not a directory: {new_path}"
        self.cwd = str(new_path)
        return f"Working directory: {self.cwd}"


def get_local_tool_schemas() -> list[dict]:
    """
    Return tool schemas for tools handled locally (not via MCP).
    These are merged with MCP tools and passed to the LLM.
    """
    return [
        {
            "name": "run_shell_command",
            "description": (
                "Execute a shell command in the current working directory. "
                "Use for: running tests (pytest, npm test), installing packages, "
                "compiling code, git operations, checking file contents with cat/grep, "
                "listing directories, etc. Output is returned as a string."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Max seconds to wait (default: 60).",
                        "default": 60,
                    },
                },
                "required": ["command"],
            },
        },
        {
            "name": "change_directory",
            "description": (
                "Change the working directory for subsequent shell commands. "
                "Use when you need to run commands from a different directory."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative or absolute path to change to.",
                    }
                },
                "required": ["path"],
            },
        },
    ]
