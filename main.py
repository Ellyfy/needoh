"""
main.py
CLI entrypoint and REPL for Needoh (run from repository root).

Usage:
    python main.py
    python main.py --provider ollama --model llama3
    python main.py --auto
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Repo root on sys.path so agent/mcpclient/ui import even if cwd differs
_REPO_ROOT = Path(__file__).resolve().parent
_rp = str(_REPO_ROOT)
if _rp not in sys.path:
    sys.path.insert(0, _rp)

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

# Load .env before importing anything that reads env vars
load_dotenv()

from agent.loop import AgentLoop
from agent.providers import get_provider
from mcpclient.client import NeedohMCPClient
from ui.display import (
    console,
    print_banner,
    print_error,
    print_help,
    print_info,
    print_mode_toggle,
    print_provider_info,
    print_success,
    ACCENT,
    DIM,
)


# ── prompt_toolkit style ──────────────────────────────────────────────────────
PROMPT_STYLE = Style.from_dict({
    "prompt": "bold ansiyellow",
})


# ── Slash command handler ─────────────────────────────────────────────────────

def handle_slash_command(
    cmd: str,
    loop: AgentLoop,
    state: dict,
) -> bool:
    """
    Handle /slash commands in the REPL.

    Args:
        cmd:   The raw input string starting with /
        loop:  The active AgentLoop (may be mutated)
        state: Mutable state dict shared with the REPL (provider, model, auto)

    Returns:
        True if the REPL should continue, False if it should exit.
    """
    parts = cmd.strip().split()
    command = parts[0].lower()

    if command == "/exit":
        print_info("Goodbye. 👋")
        return False

    elif command == "/help":
        print_help()

    elif command == "/clear":
        loop.clear_history()
        print_success("Conversation history cleared.")

    elif command == "/auto":
        loop.auto = not loop.auto
        state["auto"] = loop.auto
        print_mode_toggle(loop.auto)

    elif command == "/provider":
        if len(parts) < 2:
            print_error("Usage: /provider groq|ollama")
        else:
            new_provider_name = parts[1].lower()
            model = parts[2] if len(parts) > 2 else None
            try:
                new_provider = get_provider(new_provider_name, model=model)
                loop.provider = new_provider
                state["provider"] = new_provider_name
                state["model"] = new_provider.model
                print_success(
                    f"Switched to {new_provider_name.upper()} / {new_provider.model}"
                )
            except ValueError as exc:
                print_error(str(exc))

    elif command == "/model":
        if len(parts) < 2:
            print_error("Usage: /model <model-name>")
        else:
            model_name = parts[1]
            try:
                new_provider = get_provider(state["provider"], model=model_name)
                loop.provider = new_provider
                state["model"] = model_name
                print_success(f"Model set to {model_name}")
            except Exception as exc:
                print_error(str(exc))

    else:
        print_error(f"Unknown command '{command}'. Type /help for commands.")

    return True


# ── Main async entrypoint ─────────────────────────────────────────────────────

async def run_repl(
    provider_name: str,
    model: str | None,
    auto: bool,
) -> None:
    """Start the Needoh REPL."""
    print_banner()

    # Initialise provider
    try:
        provider = get_provider(provider_name, model=model)
    except ValueError as exc:
        print_error(str(exc))
        sys.exit(1)

    effective_model = provider.model
    print_provider_info(provider_name, effective_model, auto)
    print_info("Type your task, or /help for commands.\n")

    # Connect to all MCP servers
    async with NeedohMCPClient() as mcp_client:
        console.print()  # spacing after connection messages

        # Build the agentic loop
        agent = AgentLoop(provider=provider, mcp_client=mcp_client, auto=auto)

        # Shared mutable state for slash commands to update
        state = {
            "provider": provider_name,
            "model": effective_model,
            "auto": auto,
        }

        # prompt_toolkit session for rich input (history, arrow keys)
        session: PromptSession = PromptSession(
            history=InMemoryHistory(),
            style=PROMPT_STYLE,
        )

        while True:
            try:
                user_input = await session.prompt_async(
                    [("class:prompt", "\n⚙  you › ")]
                )
            except (EOFError, KeyboardInterrupt):
                print_info("\nInterrupted. Type /exit to quit.")
                continue

            user_input = user_input.strip()
            if not user_input:
                continue

            # ── Slash commands ────────────────────────────────────────────────
            if user_input.startswith("/"):
                should_continue = handle_slash_command(user_input, agent, state)
                if not should_continue:
                    break
                continue

            # ── Task → agentic loop ───────────────────────────────────────────
            try:
                await agent.run(user_input)
            except KeyboardInterrupt:
                print_info("\nTask interrupted. Ready for next task.")
            except Exception as exc:
                print_error(f"Unexpected error: {exc}")
                console.print_exception(show_locals=False)


# ── CLI argument parsing ──────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="needoh",
        description="Needoh — Autonomous CLI Coding Assistant",
    )
    parser.add_argument(
        "--provider",
        default=os.getenv("DEFAULT_PROVIDER", "groq"),
        choices=["groq", "ollama"],
        help="LLM provider to use (default: groq)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name override (e.g. openai/gpt-oss-20b, llama-3.1-8b-instant, llama3)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        default=os.getenv("AUTO_EXECUTE", "false").lower() == "true",
        help="Auto-execute tools without confirmation prompts",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_repl(
        provider_name=args.provider,
        model=args.model,
        auto=args.auto,
    ))


if __name__ == "__main__":
    main()
