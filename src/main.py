import hashlib
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from extractor import extract_jd
from ingestor import chunk_text, ingest_path, load_text, SUPPORTED_SUFFIXES
from reports import generate_report
from responder import answer as generate_answer
from storage import init_db, save_job, list_jobs, fetch_job, hash_exists

console = Console()


@click.group()
def cli():
    init_db()


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


@cli.command()
@click.argument("path")
def add(path):
    """Extract and save job description(s) from a file or folder."""
    p = Path(path)
    files = sorted(p.rglob("*.txt")) if p.is_dir() else [p]

    if not files:
        console.print("[yellow]No .txt files found.[/yellow]")
        return

    processed = skipped = 0

    for file in files:
        file_hash = _md5(file)

        if hash_exists(file_hash):
            console.print(f"[yellow]Skipped[/yellow] {file.name} (already processed)")
            skipped += 1
            continue

        # DEBUG: raw text exactly as read from disk, before it goes to OpenAI
        raw_text = file.read_text(encoding="utf-8")
        console.print(f"[dim]Reading {file.name} ({len(raw_text)} chars)[/dim]")
        breakpoint()  # inspect: raw_text, file, file_hash

        with console.status(f"Analyzing {file.name}..."):
            data = extract_jd(str(file))

        # DEBUG: structured JSON the model extracted from raw_text
        breakpoint()  # inspect: data (dict with company/role/skills/score_breakdown/etc.)

        if "error" in data:
            console.print(f"[red]Failed[/red] {file.name}: {data['error']}")
            continue

        job_id = save_job(data, file_name=file.name, file_hash=file_hash)
        console.print(
            f"[green]Saved[/green] [bold]{data.get('role', 'Unknown role')}[/bold] "
            f"at [bold]{data.get('company', 'Unknown company')}[/bold] "
            f"(id: [cyan]{job_id}[/cyan])"
        )
        processed += 1

    if len(files) > 1:
        console.print(f"\n[bold]Summary:[/bold] {processed} processed, {skipped} skipped")


@cli.command("list")
def list_jobs_cmd():
    """List all saved job descriptions."""
    jobs = list_jobs()

    if not jobs:
        console.print("[yellow]No jobs saved yet.[/yellow]")
        return

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("ID", style="cyan", justify="right", width=4)
    table.add_column("Company", style="bold")
    table.add_column("Role")
    table.add_column("Date", style="dim")

    for job in jobs:
        date = job["created_at"][:10]
        table.add_row(str(job["id"]), job["company"] or "—", job["role"] or "—", date)

    console.print(table)


@cli.command()
@click.argument("job_id", type=int, required=False, default=None)
def show(job_id):
    """Show all details for a saved job by ID (defaults to most recent)."""
    if job_id is None:
        recent = list_jobs()
        if not recent:
            console.print("[yellow]No jobs saved yet.[/yellow]")
            return
        job_id = recent[0]["id"]

    job = fetch_job(job_id)

    if job is None:
        console.print(f"[red]No job found with id {job_id}.[/red]")
        raise SystemExit(1)

    company = job.get("company") or "Unknown"
    role = job.get("role") or "Unknown"
    title = f"[bold]{role}[/bold] at [bold cyan]{company}[/bold cyan]"

    lines = []

    def _field(label, value):
        if value is not None:
            lines.append(f"[bold]{label}:[/bold] {value}")

    def _list_field(label, values):
        if values:
            items = "  " + "\n  ".join(f"• {v}" for v in values)
            lines.append(f"[bold]{label}:[/bold]\n{items}")

    _field("Level", job.get("level"))
    _field("Experience", f"{job['experience_years']} years" if job.get("experience_years") else None)
    _field("Match score", f"{job['match_score']}/100" if job.get("match_score") is not None else None)
    _field("Summary", job.get("summary"))
    lines.append("")
    _list_field("Required skills", job.get("required_skills"))
    _list_field("Nice to have", job.get("nice_to_have_skills"))
    _list_field("Tech stack", job.get("tech_stack"))
    _list_field("Culture signals", job.get("culture_signals"))
    _list_field("Red flags", job.get("red_flags"))

    console.print(Panel("\n".join(lines), title=title, border_style="cyan"))

    breakdown = job.get("score_breakdown")
    if breakdown:
        _COMPONENTS = [
            ("tech_stack_match",  "Tech stack match",  30),
            ("seniority_match",   "Seniority match",   20),
            ("domain_relevance",  "Domain relevance",  20),
            ("ai_skill_gap",      "AI skill gap",      15),
            ("culture_logistics", "Culture / logistics", 15),
        ]
        bd_table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold cyan")
        bd_table.add_column("Component", style="bold")
        bd_table.add_column("Score", justify="right", style="cyan")
        bd_table.add_column("Reason")

        for key, label, max_pts in _COMPONENTS:
            entry = breakdown.get(key, {})
            score = entry.get("score", "—")
            reason = entry.get("reason", "")
            bd_table.add_row(label, f"{score}/{max_pts}", reason)

        console.print(Panel(bd_table, title="[bold]Score Breakdown[/bold]", border_style="cyan"))


@cli.command()
def report():
    """Generate an aggregate report across all saved jobs."""
    generate_report()


@cli.command()
@click.argument("path")
def ingest(path):
    """Ingest a file or folder (.txt/.pdf) into the vector store."""
    p = Path(path)
    files = sorted(f for f in p.rglob("*") if f.suffix.lower() in SUPPORTED_SUFFIXES) if p.is_dir() else [p]

    # DEBUG: preview exactly what's read from each file and how it gets chunked
    for file in files:
        raw_text = load_text(file)
        chunks = chunk_text(raw_text)
        console.print(f"[dim]{file.name}: {len(raw_text)} chars -> {len(chunks)} chunks[/dim]")
        breakpoint()  # inspect: raw_text (full extracted text), chunks (list of 500-token pieces)

    with console.status(f"Ingesting {path}..."):
        summary = ingest_path(path)

    # DEBUG: per-file ingest/skip/fail outcome
    breakpoint()  # inspect: summary["results"] (list of {file, status, error})

    for r in summary["results"]:
        if r["status"] == "ingested":
            console.print(f"[green]Ingested[/green] {r['file']}")
        elif r["status"] == "skipped":
            console.print(f"[yellow]Skipped[/yellow] {r['file']} (already ingested)")
        else:
            console.print(f"[red]Failed[/red] {r['file']}: {r['error']}")

    console.print(
        f"\n[bold]Summary:[/bold] {summary['ingested']} ingested, "
        f"{summary['skipped']} skipped, {summary['failed']} failed"
    )


@cli.command()
@click.argument("question")
def ask(question):
    """Retrieve relevant chunks and generate a grounded answer to a question."""
    with console.status("Thinking..."):
        result = generate_answer(question)

    # DEBUG: chunks retrieved from ChromaDB (text/source/score) and the final answer/sources
    breakpoint()  # inspect: result["chunks"], result["sources"], result["answer"]

    console.print(Panel(result["answer"], title="[bold]Answer[/bold]", border_style="cyan"))

    if result["sources"]:
        sources_text = "\n".join(f"• {s}" for s in result["sources"])
        console.print(Panel(sources_text, title="[bold]Sources[/bold]", border_style="dim"))


if __name__ == "__main__":
    cli()
