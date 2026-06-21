import argparse
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rich.console import Console
from rich.table import Table

from key_manager.checker import run_check
from key_manager.config import load_config
from key_manager.errors import KeyManagerError
from key_manager.parser import import_keys
from key_manager.proxy import get_proxy
from key_manager.storage import KeyStore
from key_manager.tester import run_test

console = Console()


def _load_keys(config: dict) -> dict:
    """Load keys data using KeyStore, falling back to direct JSON read."""
    try:
        return KeyStore(config["storage"]["keys_file"], config).load()
    except Exception:
        keys_path = Path(config["storage"]["keys_file"])
        if not keys_path.exists():
            return {"keys": {}}
        with open(keys_path, encoding="utf-8") as f:
            return json.load(f)


def cmd_import(args, config):
    new, dupes, errors = import_keys(
        file_path=args.file,
        directory=args.dir or config["scan"]["directories"][0],
        batch=args.batch,
        keys_file=config["storage"]["keys_file"]
    )
    console.print(f"[green]Import complete:[/green] {new} new, {dupes} duplicates")
    for err in errors:
        console.print(f"[red]Error:[/red] {err}")


def cmd_check(args, config):
    proxy = get_proxy(config.get("proxy", ""))
    if proxy:
        console.print(f"[blue]Using proxy:[/blue] {proxy}")
    results = asyncio.run(run_check(
        keys_file=config["storage"]["keys_file"],
        results_file=config["storage"]["check_results_file"],
        logs_dir=config["storage"]["logs_dir"],
        concurrency=config["check"]["concurrency"],
        timeout=config["check"]["timeout_seconds"],
        proxy=proxy or None,
        retry_failed=config["check"]["retry_failed"],
        retry_count=config["check"]["retry_count"]
    ))
    console.print("\n[bold]Check Results[/bold]")
    console.print(f"Total: {results['total']}")
    console.print(f"Valid: {results['summary']['valid']['count']}")
    console.print(f"Invalid: {results['summary']['invalid']['count']}")
    console.print(f"Error: {results['summary']['error']['count']}")


def cmd_test(args, config):
    proxy = get_proxy(config.get("proxy", ""))
    if proxy:
        console.print(f"[blue]Using proxy:[/blue] {proxy}")
    results = asyncio.run(run_test(
        keys_file=config["storage"]["keys_file"],
        results_file=config["storage"]["test_results_file"],
        logs_dir=config["storage"]["logs_dir"],
        timeout=config["test"]["concurrency_timeout_seconds"],
        proxy=proxy or None,
        token_test=not args.skip_token,
        concurrency_test=not args.skip_concurrency,
        token_steps=config["test"]["token_steps"],
        concurrency_steps=config["test"]["concurrency_steps"],
        provider_filter=args.provider,
        single_key=args.key
    ))
    console.print("\n[bold]Test Results[/bold]")
    console.print(f"Total tested: {results['total_tested']}")


def cmd_list(args, config):
    keys_path = Path(config["storage"]["keys_file"])
    if not keys_path.exists():
        console.print("[yellow]No keys file found. Run 'import' first.[/yellow]")
        return

    try:
        data = _load_keys(config)
    except KeyManagerError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        return

    table = Table(title="API Keys")
    table.add_column("Key", style="cyan")
    table.add_column("Provider", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Last Checked")
    table.add_column("Max Token")
    table.add_column("Concurrency")
    table.add_column("Sources", justify="right")

    for _key, info in data["keys"].items():
        if args.provider and info["provider"].lower() != args.provider.lower():
            continue
        if args.status and info["status"] != args.status:
            continue
        if args.batch:
            has_batch = any(s.get("batch") == args.batch for s in info.get("sources", []))
            if not has_batch:
                continue

        status_style = {
            "valid": "[green]valid[/green]",
            "invalid": "[red]invalid[/red]",
            "error": "[red]error[/red]",
        }.get(info["status"], f"[yellow]{info['status']}[/yellow]")

        tests = info.get("tests", {})
        max_tokens = str(tests.get("max_tokens", "-")) if tests.get("max_tokens") else "-"
        max_conc = str(tests.get("max_concurrency", "-")) if tests.get("max_concurrency") else "-"

        table.add_row(
            info["key_masked"],
            info["provider"],
            status_style,
            info.get("last_checked", "never") or "never",
            max_tokens,
            max_conc,
            str(len(info.get("sources", [])))
        )

    console.print(table)


def cmd_report(args, config):
    keys_path = Path(config["storage"]["keys_file"])
    if not keys_path.exists():
        console.print("[yellow]No keys file found.[/yellow]")
        return

    try:
        data = _load_keys(config)
    except KeyManagerError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        return

    days = args.days or 7
    datetime.now(timezone.utc) - timedelta(days=days)

    stats = {}
    for _key, info in data["keys"].items():
        provider = info["provider"]
        if provider not in stats:
            stats[provider] = {"total": 0, "valid": 0, "invalid": 0, "error": 0, "max_tokens": [], "concurrency": []}
        stats[provider]["total"] += 1
        status = info.get("status", "unknown")
        if status in stats[provider]:
            stats[provider][status] += 1
        tests = info.get("tests", {})
        if tests.get("max_tokens"):
            stats[provider]["max_tokens"].append(tests["max_tokens"])
        if tests.get("max_concurrency"):
            stats[provider]["concurrency"].append(tests["max_concurrency"])

    table = Table(title=f"Key Statistics (last {days} days)")
    table.add_column("Provider", style="green")
    table.add_column("Total", justify="right")
    table.add_column("Valid", justify="right", style="green")
    table.add_column("Invalid", justify="right", style="red")
    table.add_column("Error", justify="right", style="red")
    table.add_column("MaxToken")
    table.add_column("Concurrency")

    total_all = 0
    total_valid = 0
    total_invalid = 0
    total_error = 0

    for provider, s in sorted(stats.items()):
        total_all += s["total"]
        total_valid += s["valid"]
        total_invalid += s["invalid"]
        total_error += s["error"]

        max_tokens = max(s["max_tokens"]) if s["max_tokens"] else "-"
        max_conc = max(s["concurrency"]) if s["concurrency"] else "-"

        table.add_row(
            provider,
            str(s["total"]),
            str(s["valid"]),
            str(s["invalid"]),
            str(s["error"]),
            str(max_tokens),
            str(max_conc)
        )

    table.add_section()
    table.add_row(
        "TOTAL",
        str(total_all),
        str(total_valid),
        str(total_invalid),
        str(total_error),
        "-", "-"
    )

    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="API Key Manager")
    subparsers = parser.add_subparsers(dest="command")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import API keys")
    import_parser.add_argument("--file", help="JSON file to import")
    import_parser.add_argument("--dir", help="Directory to scan")
    import_parser.add_argument("--batch", help="Batch label")

    # Check command
    check_parser = subparsers.add_parser("check", help="Validate keys")
    check_parser.add_argument("--provider", help="Filter by provider")
    check_parser.add_argument("--status", help="Filter by status")
    check_parser.add_argument("--key", help="Check single key")

    # Test command
    test_parser = subparsers.add_parser("test", help="Token/concurrency test")
    test_parser.add_argument("--skip-token", action="store_true", help="Skip token test")
    test_parser.add_argument("--skip-concurrency", action="store_true", help="Skip concurrency test")
    test_parser.add_argument("--provider", help="Filter by provider")
    test_parser.add_argument("--key", help="Test single key")

    # List command
    list_parser = subparsers.add_parser("list", help="List keys")
    list_parser.add_argument("--provider", help="Filter by provider")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.add_argument("--batch", help="Filter by batch")

    # Report command
    report_parser = subparsers.add_parser("report", help="Show statistics")
    report_parser.add_argument("--days", type=int, help="Days to include")

    args = parser.parse_args()
    config = load_config()

    if args.command == "import":
        cmd_import(args, config)
    elif args.command == "check":
        cmd_check(args, config)
    elif args.command == "test":
        cmd_test(args, config)
    elif args.command == "list":
        cmd_list(args, config)
    elif args.command == "report":
        cmd_report(args, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
