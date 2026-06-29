from collections import Counter

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from storage import fetch_all_jobs

console = Console()


def _freq_table(title: str, counter: Counter, top_n: int) -> Table:
    table = Table(title=title, box=box.SIMPLE_HEAD, show_header=True,
                  header_style="bold cyan", title_style="bold")
    table.add_column("Item", style="bold")
    table.add_column("JDs", justify="right", style="cyan")

    for item, count in counter.most_common(top_n):
        table.add_row(item, str(count))
    return table


def generate_report() -> None:
    jobs = fetch_all_jobs()

    if not jobs:
        console.print("[yellow]No jobs in the database yet.[/yellow]")
        return

    total = len(jobs)
    console.print(Panel(f"[bold]Aggregate report across [cyan]{total}[/cyan] saved job(s)[/bold]",
                        border_style="cyan"))

    # ── a. Skills frequency ───────────────────────────────────────────────────
    skills_counter: Counter = Counter()
    for job in jobs:
        skills_counter.update(s.strip() for s in job["required_skills"] if s.strip())

    if skills_counter:
        console.print(_freq_table("Required Skills Frequency", skills_counter, top_n=15))
    else:
        console.print("[dim]No required skills data.[/dim]")

    # ── b. Tech stack frequency ───────────────────────────────────────────────
    tech_counter: Counter = Counter()
    for job in jobs:
        tech_counter.update(t.strip() for t in job["tech_stack"] if t.strip())

    if tech_counter:
        console.print(_freq_table("Tech Stack Frequency", tech_counter, top_n=10))
    else:
        console.print("[dim]No tech stack data.[/dim]")

    # ── c. Match score summary ────────────────────────────────────────────────
    scored = [j for j in jobs if j.get("match_score") is not None]
    if scored:
        avg_score = sum(j["match_score"] for j in scored) / len(scored)
        best = max(scored, key=lambda j: j["match_score"])
        worst = min(scored, key=lambda j: j["match_score"])

        score_table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold cyan")
        score_table.add_column("Metric")
        score_table.add_column("Score", justify="right", style="cyan")
        score_table.add_column("Role / Company")

        score_table.add_row("Average", f"{avg_score:.1f}", f"({len(scored)} jobs)")
        score_table.add_row(
            "[green]Highest[/green]",
            f"[green]{best['match_score']}[/green]",
            f"{best.get('role', '?')} @ {best.get('company', '?')}",
        )
        score_table.add_row(
            "[red]Lowest[/red]",
            f"[red]{worst['match_score']}[/red]",
            f"{worst.get('role', '?')} @ {worst.get('company', '?')}",
        )
        console.print(Panel(score_table, title="[bold]Match Score Summary[/bold]", border_style="cyan"))
    else:
        console.print("[dim]No match score data.[/dim]")

    # ── d. Experience summary ─────────────────────────────────────────────────
    exp_values = [j["experience_years"] for j in jobs if j.get("experience_years") is not None]
    if exp_values:
        avg_exp = sum(exp_values) / len(exp_values)
        console.print(Panel(
            f"Average experience requested: [bold cyan]{avg_exp:.1f} years[/bold cyan] "
            f"(from {len(exp_values)} of {total} job(s))",
            title="[bold]Experience Summary[/bold]",
            border_style="cyan",
        ))
    else:
        console.print("[dim]No experience data.[/dim]")

    # ── e. Red flags ──────────────────────────────────────────────────────────
    flags_counter: Counter = Counter()
    for job in jobs:
        flags_counter.update(f.strip() for f in job["red_flags"] if f.strip())

    if flags_counter:
        console.print(_freq_table("Red Flags", flags_counter, top_n=len(flags_counter)))
    else:
        console.print("[dim]No red flags recorded.[/dim]")

    # ── f. Level breakdown ────────────────────────────────────────────────────
    level_order = ["Junior", "Mid", "Senior", "Staff", "Principal"]
    level_counter: Counter = Counter()
    for job in jobs:
        lvl = (job.get("level") or "Unknown").strip()
        level_counter[lvl] += 1

    level_table = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold cyan")
    level_table.add_column("Level", style="bold")
    level_table.add_column("Count", justify="right", style="cyan")

    for level in level_order:
        if level in level_counter:
            level_table.add_row(level, str(level_counter[level]))
    for level, count in sorted(level_counter.items()):
        if level not in level_order:
            level_table.add_row(level, str(count))

    console.print(Panel(level_table, title="[bold]Level Breakdown[/bold]", border_style="cyan"))
