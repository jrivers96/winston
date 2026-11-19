"""Main CLI application."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

import typer
from rich.console import Console
from rich.table import Table

from winston import __version__
from winston.config import get_settings

app = typer.Typer(
    name="winston",
    help="Winston - An operations agent that manages system context over time",
    no_args_is_help=True,
)
console = Console()

# Sub-command groups
issues_app = typer.Typer(help="Manage issues")
repos_app = typer.Typer(help="Manage repository registry")
context_app = typer.Typer(help="Context operations")

app.add_typer(issues_app, name="issues")
app.add_typer(repos_app, name="repos")
app.add_typer(context_app, name="context")


def _output_json(data: dict) -> None:
    """Output data as JSON."""
    console.print_json(json.dumps(data, default=str))


def _output_text(message: str) -> None:
    """Output text message."""
    console.print(message)


@app.command()
def version() -> None:
    """Show Winston version."""
    console.print(f"winston {__version__}")


@app.command()
def doctor(
    profile: Annotated[
        str, typer.Option("--profile", "-p", help="Profile to check")
    ] = "synthetic",
    output_format: Annotated[
        str, typer.Option("--format", "-f", help="Output format (text/json)")
    ] = "text",
) -> None:
    """Check Winston configuration and connectivity."""
    from winston.storage.database import check_connection
    from winston.cli.doctor import run_doctor
    
    results = run_doctor(profile)
    
    if output_format == "json":
        _output_json(results)
    else:
        _print_doctor_results(results)


def _print_doctor_results(results: dict) -> None:
    """Print doctor results in human-readable format."""
    console.print("\n[bold]Winston Doctor[/bold]\n")
    
    # Database
    db = results.get("database", {})
    db_status = "✓" if db.get("connected") else "✗"
    db_color = "green" if db.get("connected") else "red"
    console.print(f"  [{db_color}]{db_status}[/{db_color}] Database: {db.get('status', 'unknown')}")
    if db.get("version"):
        console.print(f"      Version: {db.get('version')}")
    if db.get("error"):
        console.print(f"      [red]Error: {db.get('error')}[/red]")
    
    # Directories
    dirs = results.get("directories", {})
    console.print("\n  Directories:")
    for name, info in dirs.items():
        status = "✓" if info.get("exists") else "✗"
        color = "green" if info.get("exists") else "yellow"
        console.print(f"    [{color}]{status}[/{color}] {name}: {info.get('path', 'unknown')}")
    
    # Profile
    profile = results.get("profile", {})
    profile_status = "✓" if profile.get("loaded") else "✗"
    profile_color = "green" if profile.get("loaded") else "red"
    console.print(f"\n  [{profile_color}]{profile_status}[/{profile_color}] Profile: {profile.get('name', 'unknown')}")
    if profile.get("error"):
        console.print(f"      [red]Error: {profile.get('error')}[/red]")
    
    # Repositories
    repos = results.get("repositories", {})
    console.print(f"\n  Repositories: {repos.get('count', 0)} registered")
    for repo in repos.get("items", []):
        repo_status = "✓" if repo.get("accessible") else "?"
        console.print(f"    [{repo_status}] {repo.get('id')}: {repo.get('role')}")
    
    # Overall
    console.print()
    if results.get("healthy"):
        console.print("[green]✓ Winston is healthy[/green]")
    else:
        console.print("[yellow]⚠ Winston has configuration issues[/yellow]")


@app.command()
def init(
    force: Annotated[
        bool, typer.Option("--force", help="Force initialization even if already initialized")
    ] = False,
) -> None:
    """Initialize Winston database and directories."""
    from winston.storage.database import init_database, check_connection
    from winston.config import get_settings
    
    settings = get_settings()
    
    # Check connection first
    console.print("Checking database connection...")
    conn_result = check_connection()
    if not conn_result.get("connected"):
        console.print(f"[red]Cannot connect to database: {conn_result.get('error')}[/red]")
        console.print("\nMake sure PostgreSQL is running:")
        console.print("  docker compose up -d")
        raise typer.Exit(1)
    
    # Create directories
    console.print("Creating directories...")
    for dir_name in ["artifacts_dir", "cache_dir", "fixtures_dir", "exports_dir"]:
        dir_path = getattr(settings, dir_name)
        dir_path.mkdir(parents=True, exist_ok=True)
        console.print(f"  Created {dir_path}")
    
    # Run migrations
    console.print("Running database migrations...")
    try:
        init_database()
        console.print("[green]✓ Database initialized[/green]")
    except Exception as e:
        console.print(f"[red]Migration failed: {e}[/red]")
        raise typer.Exit(1)
    
    console.print("\n[green]Winston initialized successfully![/green]")


@app.command()
def sync(
    index: Annotated[str, typer.Option("--index", "-i", help="Index to sync")],
    from_date: Annotated[str, typer.Option("--from", help="Start date")],
    to_date: Annotated[str, typer.Option("--to", help="End date")],
    profile: Annotated[str, typer.Option("--profile", "-p")] = "synthetic",
) -> None:
    """Sync execution data for an index and date range."""
    console.print(f"Syncing {index} from {from_date} to {to_date} using profile {profile}")
    # Phase 2 implementation
    console.print("[yellow]Sync command will be implemented in Phase 2[/yellow]")


@app.command()
def diagnose(
    index: str = typer.Option(..., "--index", "-i", help="Index to diagnose"),
    date: str = typer.Option(..., "--date", "-d", help="Business date"),
    scenario: str = typer.Option("as_executed", "--scenario", "-s"),
    profile: str = typer.Option("synthetic", "--profile", "-p"),
    output_format: str = typer.Option("text", "--format", "-f"),
) -> None:
    """Diagnose calculation issues for an index and date."""
    from winston.evaluation.diagnose import diagnose_index_date

    try:
        report = diagnose_index_date(
            index_id=index,
            business_date=date,
            scenario=scenario,
            profile=profile,
        )
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    if output_format == "json":
        _output_json(report)
    else:
        console.print(f"\n[bold]Diagnosis[/bold] {index}/{date} ({scenario})")
        console.print(f"  Profile: {profile}")
        console.print(f"  Execution: {report.get('execution_id', 'missing')}")
        console.print(f"  Status: {report.get('status')}")
        if report.get("state"):
            console.print(f"  State: {report['state']}")
        if report.get("findings"):
            console.print("  Findings:")
            for finding in report["findings"]:
                console.print(f"    - {finding}")


@app.command()
def impact(
    change: str = typer.Option(..., "--change", "-c", help="Change ID"),
    through: str = typer.Option(..., "--through", "-t", help="End date"),
    profile: str = typer.Option("supercalc_synthetic", "--profile", "-p"),
    output_format: str = typer.Option("text", "--format", "-f"),
) -> None:
    """Assess impact of a change."""
    from winston.evaluation.diagnose import assess_change_impact

    try:
        report = assess_change_impact(
            change_id=change,
            through_date=through,
            profile=profile,
        )
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    if output_format == "json":
        _output_json(report)
    else:
        console.print(f"\n[bold]Impact[/bold] change={change} through={through}")
        console.print(f"  Affected indices: {', '.join(report.get('affected_indices', []))}")
        console.print(f"  Affected dates: {', '.join(report.get('affected_dates', []))}")
        console.print(
            f"  Unrelated excluded: {report.get('unrelated_excluded', False)}"
        )


@app.command()
def replay(
    case: str = typer.Option("list", "--case", "-c", help="Test case name or 'list'"),
    bundle: Optional[str] = typer.Option(
        None, "--bundle", "-b", help="Recorded bundle path or sample name"
    ),
    offline: bool = typer.Option(True, "--offline/--live", help="Offline fixture mode"),
    output_format: str = typer.Option("text", "--format", "-f", help="Output format"),
) -> None:
    """Replay a named offline evaluation case or recorded bundle."""
    from winston.evaluation.cases import list_cases, run_case

    if case == "list" and not bundle:
        cases = list_cases()
        if output_format == "json":
            _output_json({"cases": cases})
        else:
            console.print("\n[bold]Known offline cases / recorded bundles[/bold]")
            for case_id, description in cases.items():
                console.print(f"  {case_id}: {description}")
        return

    try:
        report = run_case(case if not bundle else "recorded", offline=offline, bundle=bundle)
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except AssertionError as e:
        console.print(f"[red]Case assertions failed: {e}[/red]")
        raise typer.Exit(1)

    label = bundle or case
    if output_format == "json":
        _output_json(report)
    else:
        console.print(f"\n[bold]Replay[/bold] {label} ({'offline' if offline else 'live'})")
        console.print(f"  Passed: {report.get('passed')}")
        console.print(f"  Capability: {report.get('capability_label')}")
        if report.get("source"):
            console.print(f"  Source: {report.get('source')}")
        impact_info = report.get("impact", {})
        if impact_info:
            console.print(
                f"  Affected indices: {', '.join(impact_info.get('affected_indices', []))}"
            )
            if "affected_dates" in impact_info:
                console.print(
                    f"  Affected dates: {', '.join(impact_info.get('affected_dates', []))}"
                )
            if "unrelated_excluded" in impact_info:
                console.print(
                    f"  Unrelated excluded: {impact_info.get('unrelated_excluded')}"
                )
        assertions = report.get("assertions", {})
        if assertions:
            console.print("  Assertions:")
            for name, ok in assertions.items():
                mark = "✓" if ok else "✗"
                color = "green" if ok else "red"
                console.print(f"    [{color}]{mark}[/{color}] {name}")

    if not report.get("passed", False):
        raise typer.Exit(1)


@app.command()
def record(
    case: str = typer.Option(
        "supercalc-late-correction",
        "--case",
        "-c",
        help="Synthetic case to record",
    ),
    output: str = typer.Option(
        ...,
        "--output",
        "-o",
        help="Output directory for the recorded bundle",
    ),
    output_format: str = typer.Option("text", "--format", "-f"),
) -> None:
    """Record an allowlisted offline fixture bundle (no secrets/P&L)."""
    from pathlib import Path

    from winston.evaluation.recorded import record_supercalc_late_correction

    output_path = Path(output)
    try:
        if case in ("supercalc-late-correction", "supercalc-stress-s2-correction"):
            written = record_supercalc_late_correction(output_path)
        else:
            console.print(
                f"[red]Recording not implemented for case '{case}'. "
                "Supported: supercalc-late-correction[/red]"
            )
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Record failed: {e}[/red]")
        raise typer.Exit(1)

    payload = {
        "case": case,
        "output": str(written),
        "capability_label": "fixture-verified",
        "policy": {
            "credentials_excluded": True,
            "customer_pnl_excluded": True,
        },
    }
    if output_format == "json":
        _output_json(payload)
    else:
        console.print(f"[green]✓ Recorded bundle[/green] {written}")
        console.print("  Secrets/P&L excluded by policy")


@app.command(name="repair-plan")
def repair_plan(
    issue: Annotated[str, typer.Option("--issue", "-i", help="Issue ID")],
    through: Annotated[str, typer.Option("--through", "-t", help="End date")],
    output_format: Annotated[str, typer.Option("--format", "-f")] = "text",
) -> None:
    """Generate a repair plan for an issue."""
    console.print(f"Generating repair plan for issue {issue} through {through}")
    # Phase 2 implementation
    console.print("[yellow]Repair plan command will be implemented in Phase 2[/yellow]")


@app.command()
def maintain(
    once: Annotated[bool, typer.Option("--once", help="Run maintenance once")] = True,
) -> None:
    """Run maintenance tasks."""
    console.print("Running maintenance tasks...")
    # Phase 2 implementation
    console.print("[yellow]Maintain command will be implemented in Phase 2[/yellow]")


@app.command(name="export")
def export_data(
    output: Annotated[Path, typer.Option("--output", "-o", help="Output path")],
) -> None:
    """Export Winston data to a bundle."""
    from winston.cli.export_import import export_bundle
    
    console.print(f"Exporting to {output}...")
    try:
        result = export_bundle(output)
        console.print(f"[green]✓ Exported {result['issue_count']} issues, {result['artifact_count']} artifacts[/green]")
        console.print(f"  Bundle: {result['path']}")
    except Exception as e:
        console.print(f"[red]Export failed: {e}[/red]")
        raise typer.Exit(1)


@app.command(name="import")
def import_data(
    input_path: Annotated[Path, typer.Argument(help="Bundle path to import")],
    force: Annotated[bool, typer.Option("--force", help="Force import")] = False,
) -> None:
    """Import Winston data from a bundle."""
    from winston.cli.export_import import import_bundle
    
    console.print(f"Importing from {input_path}...")
    try:
        result = import_bundle(input_path, force=force)
        console.print(f"[green]✓ Imported {result['issue_count']} issues[/green]")
    except Exception as e:
        console.print(f"[red]Import failed: {e}[/red]")
        raise typer.Exit(1)


# Issues sub-commands
@issues_app.command("list")
def issues_list(
    state: Annotated[Optional[str], typer.Option("--state", "-s")] = None,
    output_format: Annotated[str, typer.Option("--format", "-f")] = "text",
) -> None:
    """List all issues."""
    from winston.storage.database import get_session
    from winston.storage.repositories import IssueRepository
    from winston.domain import IssueState
    
    with get_session() as session:
        repo = IssueRepository(session)
        
        if state:
            issues = repo.list_by_state(IssueState(state))
        else:
            issues = repo.list_all()
    
    if output_format == "json":
        _output_json({"issues": [i.model_dump() for i in issues]})
    else:
        if not issues:
            console.print("No issues found.")
            return
        
        table = Table(title="Issues")
        table.add_column("ID", style="cyan")
        table.add_column("Title")
        table.add_column("State")
        table.add_column("Severity")
        table.add_column("Index")
        table.add_column("Created")
        
        for issue in issues:
            table.add_row(
                str(issue.id)[:12],
                issue.title[:40],
                issue.state.value,
                issue.severity,
                str(issue.index_id) if issue.index_id else "-",
                issue.created_at.strftime("%Y-%m-%d %H:%M"),
            )
        
        console.print(table)


@issues_app.command("show")
def issues_show(
    issue_id: Annotated[str, typer.Argument(help="Issue ID")],
    output_format: Annotated[str, typer.Option("--format", "-f")] = "text",
) -> None:
    """Show details of an issue."""
    from winston.storage.database import get_session
    from winston.storage.repositories import IssueRepository, ObligationRepository
    from winston.domain import IssueId
    
    with get_session() as session:
        issue_repo = IssueRepository(session)
        obligation_repo = ObligationRepository(session)
        
        issue = issue_repo.get(IssueId(issue_id))
        
        if issue is None:
            console.print(f"[red]Issue not found: {issue_id}[/red]")
            raise typer.Exit(1)
        
        obligations = obligation_repo.list_by_issue(issue.id)
    
    if output_format == "json":
        _output_json({
            "issue": issue.model_dump(),
            "obligations": [o.model_dump() for o in obligations],
        })
    else:
        console.print(f"\n[bold]Issue: {issue.id}[/bold]\n")
        console.print(f"  Title: {issue.title}")
        console.print(f"  State: {issue.state.value}")
        console.print(f"  Severity: {issue.severity}")
        console.print(f"  Description: {issue.description}")
        if issue.index_id:
            console.print(f"  Index: {issue.index_id}")
        if issue.affected_dates:
            console.print(f"  Affected Dates: {', '.join(issue.affected_dates)}")
        console.print(f"  Created: {issue.created_at}")
        console.print(f"  Updated: {issue.updated_at}")
        
        if obligations:
            console.print(f"\n  [bold]Obligations ({len(obligations)}):[/bold]")
            for ob in obligations:
                console.print(f"    - [{ob.state.value}] {ob.title}")


# Repos sub-commands
@repos_app.command("list")
def repos_list(
    output_format: Annotated[str, typer.Option("--format", "-f")] = "text",
) -> None:
    """List registered repositories."""
    from winston.cli.repos import list_repositories
    
    repos = list_repositories()
    
    if output_format == "json":
        _output_json({"repositories": repos})
    else:
        if not repos:
            console.print("No repositories registered.")
            return
        
        table = Table(title="Repositories")
        table.add_column("ID", style="cyan")
        table.add_column("Role")
        table.add_column("Type")
        table.add_column("Status")
        
        for repo in repos:
            table.add_row(
                repo["id"],
                repo["role"],
                repo["location_type"],
                "✓" if repo.get("is_accessible") else "?",
            )
        
        console.print(table)


@repos_app.command("doctor")
def repos_doctor(
    output_format: Annotated[str, typer.Option("--format", "-f")] = "text",
) -> None:
    """Check repository health."""
    from winston.cli.repos import check_repositories
    
    results = check_repositories()
    
    if output_format == "json":
        _output_json(results)
    else:
        console.print("\n[bold]Repository Health Check[/bold]\n")
        for repo in results.get("repositories", []):
            status = "✓" if repo.get("healthy") else "✗"
            color = "green" if repo.get("healthy") else "red"
            console.print(f"  [{color}]{status}[/{color}] {repo['id']}")
            if repo.get("error"):
                console.print(f"      [red]{repo['error']}[/red]")


@repos_app.command("sync")
def repos_sync(
    repo: Annotated[str, typer.Option("--repo", "-r", help="Repository ID")],
) -> None:
    """Sync a repository."""
    console.print(f"Syncing repository {repo}...")
    # Phase 2 implementation
    console.print("[yellow]Repo sync will be implemented in Phase 2[/yellow]")


@repos_app.command("inspect")
def repos_inspect(
    repo: Annotated[str, typer.Option("--repo", "-r", help="Repository ID")],
    revision: Annotated[str, typer.Option("--revision", help="Git revision")] = "HEAD",
) -> None:
    """Inspect a repository at a revision."""
    console.print(f"Inspecting repository {repo} at {revision}...")
    # Phase 2 implementation
    console.print("[yellow]Repo inspect will be implemented in Phase 2[/yellow]")


# Context sub-commands
@context_app.command("search")
def context_search(
    investigation: Annotated[str, typer.Option("--investigation", "-i")],
    query: Annotated[str, typer.Option("--query", "-q")],
) -> None:
    """Search context for an investigation."""
    console.print(f"Searching investigation {investigation} for: {query}")
    # Phase 5 implementation
    console.print("[yellow]Context search will be implemented in Phase 5[/yellow]")


@context_app.command("explain")
def context_explain(
    context_id: Annotated[str, typer.Argument(help="Context ID")],
) -> None:
    """Explain a context manifest."""
    console.print(f"Explaining context {context_id}...")
    # Phase 5 implementation
    console.print("[yellow]Context explain will be implemented in Phase 5[/yellow]")


# Chain sub-command
@app.command("chain")
def chain_show(
    index: Annotated[str, typer.Option("--index", "-i", help="Index")],
    date: Annotated[str, typer.Option("--date", "-d", help="Business date")],
    output_format: Annotated[str, typer.Option("--format", "-f")] = "text",
) -> None:
    """Show the calculation chain for an index and date."""
    console.print(f"Showing chain for {index} on {date}")
    # Phase 2 implementation
    console.print("[yellow]Chain show will be implemented in Phase 2[/yellow]")


@app.command("source-manifest")
def source_manifest_show(
    run: Annotated[str, typer.Option("--run", "-r", help="Run ID")],
    output_format: Annotated[str, typer.Option("--format", "-f")] = "text",
) -> None:
    """Show the source manifest for a run."""
    console.print(f"Showing source manifest for run {run}")
    # Phase 2 implementation
    console.print("[yellow]Source manifest show will be implemented in Phase 2[/yellow]")


if __name__ == "__main__":
    app()
