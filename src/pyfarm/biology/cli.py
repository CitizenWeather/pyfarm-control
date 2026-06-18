"""CLI entry points for pyfarm-biology."""

from __future__ import annotations

import click


@click.group()
def bio():
    """pyfarm-biology: fermentation, incubation, and lab assay control."""


@bio.command()
@click.argument("spec_file")
def validate(spec_file: str):
    """Validate a .bio.yaml spec file."""
    from pyfarm.biology.spec import load_bio_spec

    try:
        spec = load_bio_spec(spec_file)
        click.echo(f"OK: {spec.metadata.name} ({len(spec.stages)} stages)")
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@bio.command()
@click.argument("spec_file")
def start(spec_file: str):
    """Start a bio run (dry-run / simulation without hardware)."""
    from pyfarm.biology.spec import load_bio_spec

    spec = load_bio_spec(spec_file)
    click.echo(f"Starting dry-run for: {spec.metadata.name}")
    for i, stage in enumerate(spec.stages, 1):
        click.echo(
            f"  Stage {i}/{len(spec.stages)}: {stage.name} "
            f"({stage.duration.min_days}–{stage.duration.max_days} days)"
        )
        sp = stage.setpoints
        if sp.temperature_c is not None:
            click.echo(f"    temperature_c = {sp.temperature_c}")
        if sp.ph_target is not None:
            click.echo(f"    ph_target     = {sp.ph_target} ± {sp.ph_tolerance}")
        if sp.agitation_rpm is not None:
            click.echo(f"    agitation_rpm = {sp.agitation_rpm}")
    click.echo("Dry-run complete — no hardware commands issued.")


@bio.command()
@click.argument("spec_file")
@click.argument("csv_file")
def replay(spec_file: str, csv_file: str):
    """Replay recorded sensor data against a bio spec.

    CSV_FILE must have columns: timestamp_epoch,metric,value
    """
    import csv as _csv

    from pyfarm.biology.spec import load_bio_spec

    spec = load_bio_spec(spec_file)
    click.echo(f"Replaying '{csv_file}' against spec: {spec.metadata.name}")

    rows: list[dict[str, str]] = []
    try:
        with open(csv_file, newline="") as fh:
            reader = _csv.DictReader(fh)
            for row in reader:
                rows.append(row)
    except FileNotFoundError:
        raise click.ClickException(f"CSV file not found: {csv_file}")

    click.echo(f"  Loaded {len(rows)} sensor readings.")

    # Group by metric and report summary
    from collections import defaultdict

    by_metric: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        metric = row.get("metric", "unknown")
        try:
            value = float(row["value"])
            by_metric[metric].append(value)
        except (KeyError, ValueError):
            pass

    for metric, values in sorted(by_metric.items()):
        click.echo(
            f"  {metric}: {len(values)} readings, "
            f"min={min(values):.3f}, max={max(values):.3f}, "
            f"mean={sum(values)/len(values):.3f}"
        )

    click.echo("Replay complete.")
