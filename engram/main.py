"""Engram CLI.

Stage 1: a plain streaming chat REPL (no tools yet) to test the LLM client.
"""

from __future__ import annotations

import argparse
import sys

from rich.console import Console

from .config import load_config
from .llm import LLMClient, LLMError

console = Console()

SYSTEM_PROMPT = "You are Engram, a concise and helpful coding assistant."


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="engram", description="Lightweight terminal coding agent")
    parser.add_argument("--config", help="path to config.yaml (default: ./config.yaml)")
    parser.add_argument("--model", help="override the model for this session")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except RuntimeError as e:
        console.print(f"[red]Config error:[/red] {e}")
        return 1
    if args.model:
        config.model = args.model

    llm = LLMClient(config)
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    console.print(f"[bold cyan]Engram[/bold cyan] · model [green]{config.model}[/green] · /exit to quit")
    while True:
        try:
            user_input = console.input("[bold blue]you> [/bold blue]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print()
            return 0
        if not user_input:
            continue
        if user_input in ("/exit", "/quit"):
            return 0

        messages.append({"role": "user", "content": user_input})
        console.print("[bold magenta]engram>[/bold magenta] ", end="")
        try:
            reply = llm.stream_chat(
                messages,
                on_token=lambda t: console.print(t, end="", markup=False, highlight=False, soft_wrap=True),
            )
        except LLMError as e:
            console.print(f"\n[red]Error:[/red] {e}")
            messages.pop()  # drop the failed user turn so history stays valid
            continue
        except KeyboardInterrupt:
            console.print("\n[yellow]interrupted[/yellow]")
            messages.pop()
            continue
        console.print()
        messages.append(reply.to_dict())


if __name__ == "__main__":
    sys.exit(main())
