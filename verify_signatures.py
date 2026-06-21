#!/usr/bin/env python3
"""
Signature Fingerprint Verification Script
Automatically test each provider, collect error responses, verify signature accuracy
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Add project path
sys.path.insert(0, str(Path(__file__).parent))

from key_manager.providers import PROVIDERS, PROVIDER_ERROR_SIGNATURES

console = Console(force_terminal=True, width=120)

# Test configuration
INVALID_KEY = "sk-invalid-test-key-for-signature-verification-12345"
TIMEOUT_SECONDS = 10.0
MAX_BODY_LENGTH = 500


async def test_provider(
    client: httpx.AsyncClient,
    provider_name: str,
    provider,
    invalid_key: str
) -> dict:
    """Test a single provider, return results"""
    try:
        result = await asyncio.wait_for(
            provider.probe(client, invalid_key),
            timeout=TIMEOUT_SECONDS
        )
        return {
            "provider": provider_name,
            "status_code": result.status_code,
            "error": result.error,
            "response_body": result.response_body or "",
            "latency_ms": result.latency_ms,
            "valid": result.valid,
        }
    except asyncio.TimeoutError:
        return {
            "provider": provider_name,
            "status_code": None,
            "error": "timeout",
            "response_body": "",
            "latency_ms": TIMEOUT_SECONDS * 1000,
            "valid": False,
        }
    except Exception as e:
        return {
            "provider": provider_name,
            "status_code": None,
            "error": str(e),
            "response_body": "",
            "latency_ms": 0,
            "valid": False,
        }


def extract_signatures_from_body(body: str) -> list[str]:
    """Extract potential signatures from response body"""
    import re
    body_lower = body.lower()
    words = re.findall(r'[a-z0-9][a-z0-9_-]{2,}', body_lower)
    return list(set(words))


def verify_signatures(
    provider_name: str,
    response_body: str,
    unique_sigs: dict[str, list[str]],
    error_sigs: dict[str, list[str]]
) -> dict:
    """Verify signature accuracy"""
    body_lower = response_body.lower()
    
    current_unique = unique_sigs.get(provider_name, [])
    current_error = error_sigs.get(provider_name, [])
    
    unique_matched = []
    unique_missing = []
    for sig in current_unique:
        if sig.lower() in body_lower:
            unique_matched.append(sig)
        else:
            unique_missing.append(sig)
    
    error_matched = []
    error_missing = []
    for sig in current_error:
        if sig.lower() in body_lower:
            error_matched.append(sig)
        else:
            error_missing.append(sig)
    
    extracted = extract_signatures_from_body(response_body)
    known_sigs = set(s.lower() for s in current_unique + current_error)
    new_signatures = [s for s in extracted if s not in known_sigs and len(s) > 3]
    
    conflicts = []
    for other_provider, other_sigs in unique_sigs.items():
        if other_provider == provider_name:
            continue
        for sig in other_sigs:
            if sig.lower() in body_lower:
                conflicts.append({
                    "signature": sig,
                    "other_provider": other_provider,
                })
    
    return {
        "provider": provider_name,
        "unique_signatures": {
            "total": len(current_unique),
            "matched": unique_matched,
            "missing": unique_missing,
            "match_rate": len(unique_matched) / len(current_unique) if current_unique else 0,
        },
        "error_signatures": {
            "total": len(current_error),
            "matched": error_matched,
            "missing": error_missing,
            "match_rate": len(error_matched) / len(current_error) if current_error else 0,
        },
        "new_signatures": new_signatures[:10],
        "conflicts": conflicts,
    }


async def main():
    """Main function"""
    console.print(Panel.fit(
        "[bold cyan]Signature Fingerprint Verification Tool[/bold cyan]\n"
        "Automatically test each provider, collect error responses, verify signature accuracy",
        border_style="cyan"
    ))
    
    console.print(f"\n[bold]Configuration:[/bold]")
    console.print(f"  Invalid Key: {INVALID_KEY[:20]}...")
    console.print(f"  Timeout: {TIMEOUT_SECONDS}s")
    console.print(f"  Providers: {len(PROVIDERS)}")
    console.print(f"  PROVIDER_ERROR_SIGNATURES: {len(PROVIDER_ERROR_SIGNATURES)} providers")
    console.print(f"  PROVIDER_ERROR_SIGNATURES: {len(PROVIDER_ERROR_SIGNATURES)} providers")
    
    console.print(f"\n[bold cyan]Starting tests...[/bold cyan]")
    
    results = []
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=False) as client:
        tasks = []
        for provider_name, provider in PROVIDERS.items():
            tasks.append(test_provider(client, provider_name, provider, INVALID_KEY))
        
        semaphore = asyncio.Semaphore(10)
        
        async def limited_test(coro):
            async with semaphore:
                return await coro
        
        results = await asyncio.gather(*[limited_test(t) for t in tasks])
    
    console.print(f"\n[bold cyan]Verifying signatures...[/bold cyan]")
    
    verification_results = []
    for result in results:
        verification = verify_signatures(
            result["provider"],
            result["response_body"],
            PROVIDER_ERROR_SIGNATURES,
            PROVIDER_ERROR_SIGNATURES
        )
        verification["test_result"] = result
        verification_results.append(verification)
    
    console.print(f"\n[bold cyan]Generating report...[/bold cyan]")
    
    total_providers = len(verification_results)
    successful_tests = sum(1 for r in verification_results if r["test_result"]["status_code"] is not None)
    full_match = sum(1 for r in verification_results if r["unique_signatures"]["match_rate"] == 1.0)
    partial_match = sum(1 for r in verification_results if 0 < r["unique_signatures"]["match_rate"] < 1.0)
    no_match = sum(1 for r in verification_results if r["unique_signatures"]["match_rate"] == 0)
    has_conflicts = sum(1 for r in verification_results if r["conflicts"])
    has_new_sigs = sum(1 for r in verification_results if r["new_signatures"])
    
    table = Table(title="Signature Verification Results", show_lines=True)
    table.add_column("Provider", style="cyan", width=20)
    table.add_column("Status", justify="center", width=6)
    table.add_column("UNIQUE Sig", justify="center", width=12)
    table.add_column("ERROR Sig", justify="center", width=12)
    table.add_column("New", justify="center", width=6)
    table.add_column("Conflict", justify="center", width=6)
    table.add_column("Result", justify="center", width=8)
    
    for r in sorted(verification_results, key=lambda x: x["provider"]):
        provider = r["provider"]
        status_code = r["test_result"]["status_code"]
        unique_rate = r["unique_signatures"]["match_rate"]
        error_rate = r["error_signatures"]["match_rate"]
        new_sigs = len(r["new_signatures"])
        conflicts = len(r["conflicts"])
        
        if status_code is None:
            status_code_str = "[red]N/A[/red]"
        elif status_code in (401, 403):
            status_code_str = f"[yellow]{status_code}[/yellow]"
        elif status_code == 200:
            status_code_str = f"[green]{status_code}[/green]"
        else:
            status_code_str = f"[red]{status_code}[/red]"
        
        def format_rate(rate: float, total: int) -> str:
            if total == 0:
                return "[dim]N/A[/dim]"
            if rate == 1.0:
                return f"[green]OK {int(rate*total)}/{total}[/green]"
            elif rate > 0:
                return f"[yellow]WARN {int(rate*total)}/{total}[/yellow]"
            else:
                return f"[red]FAIL 0/{total}[/red]"
        
        unique_str = format_rate(unique_rate, r["unique_signatures"]["total"])
        error_str = format_rate(error_rate, r["error_signatures"]["total"])
        
        if new_sigs > 0:
            new_sigs_str = f"[yellow]+{new_sigs}[/yellow]"
        else:
            new_sigs_str = "[dim]0[/dim]"
        
        if conflicts > 0:
            conflicts_str = f"[red]!{conflicts}[/red]"
        else:
            conflicts_str = "[dim]0[/dim]"
        
        if unique_rate == 1.0 and conflicts == 0:
            status = "[green]OK[/green]"
        elif unique_rate == 1.0 and conflicts > 0:
            status = "[yellow]WARN[/yellow]"
        elif unique_rate > 0:
            status = "[yellow]PARTIAL[/yellow]"
        elif status_code is None:
            status = "[red]FAIL[/red]"
        else:
            status = "[red]NO MATCH[/red]"
        
        table.add_row(
            provider,
            status_code_str,
            unique_str,
            error_str,
            new_sigs_str,
            conflicts_str,
            status
        )
    
    console.print(table)
    
    console.print(f"\n[bold cyan]=== Detailed Report ===[/bold cyan]")
    
    console.print(f"\n[bold yellow]Missing Signatures (PROVIDER_ERROR_SIGNATURES):[/bold yellow]")
    missing_count = 0
    for r in sorted(verification_results, key=lambda x: x["provider"]):
        if r["unique_signatures"]["missing"]:
            missing_count += 1
            console.print(f"  [cyan]{r['provider']}[/cyan]: {r['unique_signatures']['missing']}")
    if missing_count == 0:
        console.print("  [green]No missing signatures[/green]")
    
    console.print(f"\n[bold yellow]New Signatures Found:[/bold yellow]")
    new_sig_count = 0
    for r in sorted(verification_results, key=lambda x: x["provider"]):
        if r["new_signatures"]:
            new_sig_count += 1
            console.print(f"  [cyan]{r['provider']}[/cyan]: {r['new_signatures'][:5]}")
    if new_sig_count == 0:
        console.print("  [green]No new signatures[/green]")
    
    console.print(f"\n[bold yellow]Signature Conflicts:[/bold yellow]")
    conflict_count = 0
    for r in sorted(verification_results, key=lambda x: x["provider"]):
        if r["conflicts"]:
            conflict_count += 1
            for conflict in r["conflicts"][:3]:
                console.print(f"  [cyan]{r['provider']}[/cyan] vs [cyan]{conflict['other_provider']}[/cyan]: '{conflict['signature']}'")
    if conflict_count == 0:
        console.print("  [green]No signature conflicts[/green]")
    
    console.print(f"\n[bold yellow]Data Inconsistencies (UNIQUE vs ERROR):[/bold yellow]")
    inconsistency_count = 0
    for r in sorted(verification_results, key=lambda x: x["provider"]):
        provider = r["provider"]
        unique_sigs = set(s.lower() for s in PROVIDER_ERROR_SIGNATURES.get(provider, []))
        error_sigs = set(s.lower() for s in PROVIDER_ERROR_SIGNATURES.get(provider, []))
        
        if unique_sigs != error_sigs:
            inconsistency_count += 1
            only_unique = unique_sigs - error_sigs
            only_error = error_sigs - unique_sigs
            if only_unique:
                console.print(f"  [cyan]{provider}[/cyan]: UNIQUE only {only_unique}")
            if only_error:
                console.print(f"  [cyan]{provider}[/cyan]: ERROR only {only_error}")
    if inconsistency_count == 0:
        console.print("  [green]Fully consistent[/green]")
    
    console.print(f"\n[bold cyan]=== Summary ===[/bold cyan]")
    console.print(f"  Total providers: {total_providers}")
    console.print(f"  Successful tests: {successful_tests}")
    console.print(f"  Full match: {full_match}")
    console.print(f"  Partial match: {partial_match}")
    console.print(f"  No match: {no_match}")
    console.print(f"  Has conflicts: {has_conflicts}")
    console.print(f"  Has new signatures: {has_new_sigs}")
    
    report_path = Path(__file__).parent / "data" / "signature_verification_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    report = {
        "generated_at": datetime.now().isoformat(),
        "config": {
            "invalid_key": INVALID_KEY[:20] + "...",
            "timeout_seconds": TIMEOUT_SECONDS,
            "max_body_length": MAX_BODY_LENGTH,
        },
        "summary": {
            "total_providers": total_providers,
            "successful_tests": successful_tests,
            "full_match": full_match,
            "partial_match": partial_match,
            "no_match": no_match,
            "has_conflicts": has_conflicts,
            "has_new_signatures": has_new_sigs,
        },
        "results": verification_results,
    }
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    console.print(f"\n[green]Report saved to: {report_path}[/green]")


if __name__ == "__main__":
    asyncio.run(main())
