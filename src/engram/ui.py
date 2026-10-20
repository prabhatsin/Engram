# Rich terminal UI for chat mode: spinner, tool lines, Markdown answers
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text
from . import loop
from rich.table import Table

# module-level so tests can swap them for Console(record=True)
console = Console()
err_console = Console(stderr=True)

# args worth showing, in order of preference
KEY_ARGS = ("path", "command", "pattern", "query")




def show_memories(facts):
    if not facts:
        console.print("[dim](No memories stored for this repo yet.)[/dim]")
        return
    table = Table(title="Stored memories (this repo)", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Memory")
    for i, fact in enumerate(facts, 1):
        table.add_row(str(i), Text(fact))      # Text(), not a plain string: a "[x]" in a fact
    console.print(table)    
                       # would otherwise be read as Rich markup
def _short(text, limit):
    """First line only, cut to `limit` chars."""
    lines = str(text).strip().splitlines()
    line = lines[0] if lines else ""
    return line if len(line) <= limit else line[: limit - 1] + "…"


def _main_arg(args):
    for key in KEY_ARGS:
        if args.get(key):
            return args[key]
    return ""


class RichHooks(loop.Hooks):
    def __init__(self):
        self._status = None

    def on_model_start(self, step):
        self.on_model_end()              # never leave an old spinner running
        self._status = console.status("Thinking…")
        self._status.start()

    def on_model_end(self):
        # safe to call twice or without a start
        if self._status is not None:
            self._status.stop()
            self._status = None

    def on_tool_call(self, name, args):
        line = Text(f"▸ {name}", style="dim")
        arg = _main_arg(args or {})
        if arg:
            line.append(f"  {_short(arg, 100)}", style="dim")
        console.print(line)

    def on_tool_result(self, name, output):
        if "error" in output:
            console.print(Text("✗ ", style="bold red") + Text(_short(output["error"], 120), style="red"))
        else:
            console.print(Text("✓ ", style="bold green") + Text(_short(output.get("result", ""), 120), style="dim"))


def banner():
    console.print(Text("Engram chat", style="bold"))
    console.print(Text("Type 'exit' to quit.", style="dim"))


def show_answer(text):
    if not text:
        console.print("(The model returned no text.)")
        return
    console.print(Markdown(text))


def show_error(msg):
    err_console.print(Text(f"Error: {msg}", style="red"))

