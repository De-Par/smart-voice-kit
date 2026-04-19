from __future__ import annotations

import argparse

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from core.formatting import format_bytes
from core.settings import load_settings
from schemas.model import ModelRequest
from schemas.runtime import ModelPreparationResult, PipelinePreparationResult
from services.prepare_model import (
    build_asr_model_request,
    build_pcs_model_request,
    build_translation_model_request,
    prepare_configured_models,
    prepare_model,
)


def _component_title(task: str, family: str, provider: str) -> str:
    return f"{task.upper()} · {family} · {provider}"


def _component_status(result: ModelPreparationResult) -> str:
    readiness = "ready" if result.ready else "not ready"
    locality = "offline-only" if result.local_files_only else "network-enabled"
    return f"{result.mode} · {readiness} · {locality}"


def _render_model_request(
    request: ModelRequest,
    *,
    index: int,
    total: int,
    console: Console,
) -> None:
    descriptor = request.descriptor
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    table.add_row("Model", descriptor.model_name)
    table.add_row("Cache", str(descriptor.download_root or "<none>"))
    table.add_row(
        "Policy",
        "force refresh" if request.force_download else "verify or download missing files",
    )
    if descriptor.task == "translation":
        table.add_row(
            "Languages",
            f"{descriptor.source_language or 'auto'} -> {descriptor.target_language or 'en'}",
        )

    console.print(
        Rule(
            f"[bold cyan]{index}/{total}[/bold cyan] "
            f"{_component_title(descriptor.task, descriptor.family, descriptor.provider)}"
        )
    )
    console.print(table)
    console.print()


def render_component_prepare_result(
    result: ModelPreparationResult,
    *,
    console: Console,
) -> None:
    table = Table(show_header=False, box=None, pad_edge=False)
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    table.add_row("Model", result.model_name)
    if result.model_source != result.model_name:
        table.add_row("Source", result.model_source)
    if result.download_root:
        table.add_row("Cache", result.download_root)
    if result.total_files or result.downloaded_files:
        table.add_row("Files", f"{result.downloaded_files}/{result.total_files}")
    if result.total_bytes or result.downloaded_bytes:
        table.add_row(
            "Traffic",
            f"{format_bytes(result.downloaded_bytes)} / {format_bytes(result.total_bytes)}",
        )
    table.add_row("Status", _component_status(result))
    if result.message:
        table.add_row("Message", result.message)
    console.print(
        Panel(
            table,
            title=_component_title(result.task, result.family, result.provider),
            border_style="green" if result.ready else "yellow",
        )
    )
    console.print()


def render_pipeline_prepare_result(
    result: PipelinePreparationResult,
    *,
    console: Console,
) -> None:
    for component in result.components:
        render_component_prepare_result(component, console=console)


def install_model(
    *,
    task: str,
    family: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    source_language: str | None = None,
    target_language: str | None = None,
    force: bool = False,
    console: Console | None = None,
) -> ModelPreparationResult:
    active_console = console or Console()
    settings = load_settings()
    if task == "asr":
        request = build_asr_model_request(
            settings,
            family=family,
            provider=provider,
            model_name=model_name,
            local_files_only=False,
            force_download=force,
        )
    elif task == "pcs":
        request = build_pcs_model_request(
            settings,
            family=family,
            provider=provider,
            model_name=model_name,
            local_files_only=False,
            force_download=force,
        )
    else:
        request = build_translation_model_request(
            settings,
            family=family,
            provider=provider,
            model_name=model_name,
            source_language=source_language,
            target_language=target_language,
            local_files_only=False,
            force_download=force,
        )
    _render_model_request(request, index=1, total=1, console=active_console)
    result = prepare_model(request, console=active_console)
    render_component_prepare_result(result, console=active_console)
    return result


def install_configured_models(
    *,
    force: bool = False,
    console: Console | None = None,
) -> PipelinePreparationResult:
    active_console = console or Console()
    settings = load_settings()
    result = prepare_configured_models(
        settings,
        force_download=force,
        console=active_console,
        on_component_started=lambda request, index, total: _render_model_request(
            request,
            index=index,
            total=total,
            console=active_console,
        ),
        on_component_prepared=lambda component: render_component_prepare_result(
            component,
            console=active_console,
        ),
    )
    return result


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ivoice-install-model",
        description=(
            "Install or verify a specific local model for iVoice. "
            "Supported tasks: asr/whisper, translation/m2m100|opus_mt, and "
            "pcs/punctuation."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    configured_parser = subparsers.add_parser(
        "configured",
        help="Install or verify the models configured in config.toml.",
    )
    configured_parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even if they are already cached.",
    )

    asr_parser = subparsers.add_parser(
        "asr",
        help="Install a concrete ASR model family for local runtime.",
    )
    asr_parser.add_argument(
        "--family",
        default="whisper",
        choices=["whisper"],
        help="ASR model family.",
    )
    asr_parser.add_argument(
        "--provider",
        default="faster_whisper",
        choices=["faster_whisper"],
        help="ASR runtime provider.",
    )
    asr_parser.add_argument(
        "--model-name",
        default=None,
        help="Concrete ASR model name, for example `base` or `small`.",
    )
    asr_parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even if they are already cached.",
    )

    translation_parser = subparsers.add_parser(
        "translation",
        help="Install a concrete translation model family for local runtime.",
    )
    translation_parser.add_argument(
        "--family",
        default="m2m100",
        choices=["m2m100", "opus_mt"],
        help="Translation model family.",
    )
    translation_parser.add_argument(
        "--provider",
        default="transformers",
        choices=["transformers"],
        help="Translation runtime provider.",
    )
    translation_parser.add_argument(
        "--model-name",
        default=None,
        help=(
            "Concrete translation model name, for example `facebook/m2m100_418M` or "
            "`Helsinki-NLP/opus-mt-ru-en`."
        ),
    )
    translation_parser.add_argument(
        "--source-language",
        default=None,
        help="Optional normalized source language label such as `ru` or `en`.",
    )
    translation_parser.add_argument(
        "--target-language",
        default=None,
        help="Optional normalized target language label such as `en`.",
    )
    translation_parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even if they are already cached.",
    )

    pcs_parser = subparsers.add_parser(
        "pcs",
        help="Install a concrete punctuation/capitalization model for local runtime.",
    )
    pcs_parser.add_argument(
        "--family",
        default="punctuation",
        choices=["punctuation"],
        help="PCS model family.",
    )
    pcs_parser.add_argument(
        "--provider",
        default="onnx",
        choices=["transformers", "onnx"],
        help="PCS runtime provider.",
    )
    pcs_parser.add_argument(
        "--model-name",
        default=None,
        help=(
            "Concrete PCS model name, for example "
            "`1-800-BAD-CODE/xlm-roberta_punctuation_fullstop_truecase`."
        ),
    )
    pcs_parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even if they are already cached.",
    )

    return parser


def run() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.command == "configured":
        install_configured_models(force=args.force)
        return

    install_model(
        task=args.command,
        family=args.family,
        provider=args.provider,
        model_name=args.model_name,
        source_language=getattr(args, "source_language", None),
        target_language=getattr(args, "target_language", None),
        force=args.force,
    )


if __name__ == "__main__":
    run()
