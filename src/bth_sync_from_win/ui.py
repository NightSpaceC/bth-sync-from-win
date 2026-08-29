from __future__ import annotations

import os
import sys


RESET = "\033[0m"

LIGHT_BLUE = "\033[94m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
WHITE = "\033[97m"


def _supports_color(stream) -> bool:
    """
    Enable colors only when outputting to a terminal.

    Also respect NO_COLOR and avoid colors on TERM=dumb.
    """
    if "NO_COLOR" in os.environ:
        return False

    if os.environ.get("TERM") == "dumb":
        return False

    try:
        return stream.isatty()
    except Exception:
        return False


def _paint(message: str, color: str, stream) -> str:
    if not _supports_color(stream):
        return message

    return f"{color}{message}{RESET}"


def info(message: str) -> None:
    print(_paint(message, CYAN, sys.stdout))


def success(message: str) -> None:
    print(_paint(message, GREEN, sys.stdout))


def warning(message: str) -> None:
    print(_paint(f"Warning: {message}", YELLOW, sys.stderr))


def error(message: str) -> None:
    print(_paint(f"Error: {message}", RED, sys.stderr))


def block(text: str) -> None:
    """
    Print file-like content.

    Use blank lines before and after the block so that it is visually
    separated from surrounding interactive messages.
    """
    print()
    print(_paint(text.rstrip("\n"), WHITE, sys.stdout))
    print()


def confirm(prompt: str, assume_yes: bool = False, dry_run: bool = False) -> bool:
    if dry_run:
        return False

    if assume_yes:
        return True

    prompt_text = f"{prompt} [y/N] "
    colored_prompt = _paint(prompt_text, LIGHT_BLUE, sys.stdout)

    try:
        sys.stdout.flush()
        answer = input(colored_prompt).strip().lower()
    except EOFError:
        print()
        return False

    return answer in {"y", "yes"}
