"""Phoenix Agent CLI - command-line interface for running refactoring."""

from __future__ import annotations

import argparse
import json
import logging
import sys

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from phoenix_agent.agent import PhoenixAgent
from phoenix_agent.config import PhoenixConfig


console = Console()


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def cmd_refactor(args: argparse.Namespace) -> None:
    """Run the refactoring agent."""
    setup_logging(args.log_level)

    console.print(Panel(
        "[bold blue]Phoenix Agent[/bold blue]\n"
        "Agentic Code Refactoring System",
        expand=False,
    ))

    config = PhoenixConfig.from_env()
    if args.max_iterations:
        config.agent.max_iterations = args.max_iterations

    console.print(f"\n[bold]Target:[/bold] {args.target}")
    console.print(f"[bold]Request:[/bold] {args.request}")
    console.print(f"[bold]Provider:[/bold] {config.llm.provider}")
    console.print(f"[bold]Model:[/bold] {config.llm.model}\n")

    agent = PhoenixAgent(config)

    try:
        result = agent.run(args.request, args.target)
    finally:
        agent.close()

    # Display result
    status = result.get("status", "unknown")
    if status == "success":
        console.print(Panel(
            f"[bold green]Refactoring Complete[/bold green]\n\n"
            f"Session: {result.get('session_id')}\n"
            f"Branch: {result.get('branch')}\n"
            f"PR: {result.get('pr_url', 'N/A')}\n"
            f"Duration: {result.get('duration_seconds', 0):.1f}s",
            border_style="green",
        ))

        # Metrics table
        if result.get("metrics_before") and result.get("metrics_after"):
            table = Table(title="Complexity Metrics")
            table.add_column("File", style="cyan")
            table.add_column("Before", justify="right")
            table.add_column("After", justify="right")
            table.add_column("Change", justify="right")

            before = result["metrics_before"]
            after = result["metrics_after"]
            for f in sorted(set(before.keys()) | set(after.keys())):
                b = before.get(f, 0)
                a = after.get(f, 0)
                delta = a - b
                color = "green" if delta < 0 else "red" if delta > 0 else "white"
                sign = "+" if delta > 0 else ""
                table.add_row(
                    f.split("/")[-1],
                    str(b),
                    str(a),
                    f"[{color}]{sign}{delta}[/{color}]",
                )
            console.print(table)

    elif status == "awaiting_approval":
        console.print(Panel(
            f"[bold yellow]Awaiting Human Approval[/bold yellow]\n\n"
            f"Session: {result.get('session_id')}\n"
            f"Risk Score: {result.get('risk_score', 0):.1f}\n"
            f"Reason: {result.get('reason')}\n"
            f"Steps: {result.get('plan_steps')}\n"
            f"Files: {result.get('files_affected')}",
            border_style="yellow",
        ))

    else:
        console.print(Panel(
            f"[bold red]Refactoring Failed[/bold red]\n\n"
            f"Session: {result.get('session_id', 'N/A')}\n"
            f"Reason: {result.get('reason', 'Unknown')}\n"
            f"Duration: {result.get('duration_seconds', 0):.1f}s",
            border_style="red",
        ))

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(result, f, indent=2, default=str)
        console.print(f"\nResult saved to {args.output_json}")


def cmd_history(args: argparse.Namespace) -> None:
    """Show refactoring history."""
    setup_logging("WARNING")
    config = PhoenixConfig.from_env()

    from phoenix_agent.memory.history import RefactoringHistory
    history = RefactoringHistory(config)

    records = history.get_history(limit=args.limit)
    if not records:
        console.print("No refactoring history found.")
        return

    table = Table(title="Refactoring History")
    table.add_column("Session", style="cyan")
    table.add_column("Outcome", style="bold")
    table.add_column("Files", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("PR", style="blue")

    for r in records:
        outcome_color = "green" if r.outcome == "success" else "red"
        table.add_row(
            r.session_id,
            f"[{outcome_color}]{r.outcome}[/{outcome_color}]",
            str(len(r.files_modified)),
            f"{r.duration_seconds:.1f}s",
            r.pr_url or "—",
        )

    console.print(table)
    history.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="phoenix-agent",
        description="Phoenix: Agentic Code Refactoring System",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # refactor command
    refactor_parser = subparsers.add_parser("refactor", help="Run refactoring agent")
    refactor_parser.add_argument("target", help="Path to project/directory to refactor")
    refactor_parser.add_argument("request", help="Refactoring request description")
    refactor_parser.add_argument("--max-iterations", type=int, help="Max agent iterations")
    refactor_parser.add_argument("--log-level", default="INFO", help="Logging level")
    refactor_parser.add_argument("--output-json", help="Save result to JSON file")
    refactor_parser.set_defaults(func=cmd_refactor)

    # history command
    history_parser = subparsers.add_parser("history", help="Show refactoring history")
    history_parser.add_argument("--limit", type=int, default=20, help="Number of records")
    history_parser.set_defaults(func=cmd_history)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
