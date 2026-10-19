# CLI entry point
import sys
from . import loop, provider


def main(argv=None):
    # sys.argv is the list of words typed after python on the command line. For python -m engram.main 
    # fix the bug it is ["engram/main.py", "fix", "the", "bug"], and the first item is the script 
    # name, so [1:] drops it.
    args = sys.argv[1:] if argv is None else argv
    prompt = " ".join(args).strip()
    if not prompt:
        print('Usage: python -m engram.main "what you want the agent to do"', file=sys.stderr)
        return 2
    try:
        answer = loop.run_agent(prompt)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except (loop.AgentError, provider.ProviderError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(answer if answer else "(The model returned no text.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# What it does:
'''
# Empty prompt: prints a usage line and exits with code 2, with no model call.

# Known failures (AgentError from the step limit, repeat detection or a model failure, plus 
  ProviderError): one clean line on stderr, exit code 1.
# Ctrl+C: prints “Interrupted.” and exits 130, the standard code. This works at the confirmation 
  prompt and during a bash command too, because the bash tool kills its process group before re-raising.

# Unexpected exceptions: deliberately not caught, so a real bug in our code still shows a traceback.

# Logic in main(): not at module level, so it can be tested without launching a process.

'''