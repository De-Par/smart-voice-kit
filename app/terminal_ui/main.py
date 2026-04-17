from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from schemas.transcription import TranscriptionRun
from services.bootstrap import build_app_context

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


def _render_result(result: TranscriptionRun) -> None:
    table = Table(show_header=False)
    table.add_row("Run ID", result.metadata.id)
    table.add_row("Timestamp", result.metadata.timestamp.isoformat())
    table.add_row("Transcript", result.metadata.transcript or "<empty>")
    table.add_row("Transcript EN", result.metadata.transcript_en or "<empty>")
    table.add_row("Language", result.metadata.language or "<unknown>")
    table.add_row("Target language", result.metadata.target_language)
    table.add_row("Duration", f"{result.metadata.duration_seconds:.2f}s")
    table.add_row("Sample rate", str(result.metadata.sample_rate))
    table.add_row("ASR inference", f"{result.metadata.inference_seconds:.2f}s")
    table.add_row("ASR family", result.metadata.asr_family)
    table.add_row("ASR provider", result.metadata.asr_provider)
    table.add_row(
        "Translation inference",
        (
            f"{result.metadata.translation_inference_seconds:.2f}s"
            if result.metadata.translation_inference_seconds is not None
            else "<disabled>"
        ),
    )
    table.add_row("Translation family", result.metadata.translation_family or "<disabled>")
    table.add_row(
        "Translation provider",
        result.metadata.translation_provider or "<disabled>",
    )
    table.add_row("Run dir", result.run_dir)
    console.print(Panel(table, title="Transcription Result"))


@app.command("transcribe-file")
def transcribe_file(
    path: Path,
    language: str | None = typer.Option(default=None, help="Optional language override."),
) -> None:
    """Transcribe a local WAV file and persist run artifacts"""

    try:
        result = build_app_context().service.transcribe_file(path, language=language)
    except Exception as error:
        console.print(f"[red]Transcription failed:[/red] {error}")
        raise typer.Exit(code=1) from error

    _render_result(result)


@app.command("transcribe-last")
def transcribe_last(
    language: str | None = typer.Option(default=None, help="Optional language override."),
) -> None:
    """Reuse the audio file from the latest run and transcribe it again"""

    try:
        result = build_app_context().service.transcribe_last(language=language)
    except Exception as error:
        console.print(f"[red]Transcription failed:[/red] {error}")
        raise typer.Exit(code=1) from error

    _render_result(result)


def run() -> None:
    app()


if __name__ == "__main__":
    run()
