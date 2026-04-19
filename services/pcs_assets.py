from __future__ import annotations

from huggingface_hub import HfApi, hf_hub_download
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from core.formatting import format_bytes
from schemas.config import PCSSettings
from schemas.runtime import ModelPreparationResult
from services.asr_assets import suppress_hf_progress_bars, suppress_hf_transfer_logs


class TransformersPCSAssetPreparer:
    def __init__(self, settings: PCSSettings, console: Console | None = None) -> None:
        self.settings = settings
        self.console = console or Console()

    @property
    def repo_id(self) -> str:
        return self.settings.model_name

    def _collect_file_infos(self) -> list[object]:
        api = HfApi()
        repo_files = sorted(api.list_repo_files(repo_id=self.repo_id, repo_type="model"))
        file_infos: list[object] = []
        with suppress_hf_transfer_logs(), suppress_hf_progress_bars():
            for filename in repo_files:
                file_infos.append(
                    hf_hub_download(
                        repo_id=self.repo_id,
                        filename=filename,
                        cache_dir=self.settings.download_root,
                        local_files_only=False,
                        dry_run=True,
                    )
                )
        return file_infos

    def prepare(self, force_download: bool = False) -> ModelPreparationResult:
        if self.settings.model_path is not None:
            if not self.settings.model_path.exists():
                raise FileNotFoundError(
                    f"Configured PCS model_path does not exist: {self.settings.model_path}"
                )
            return ModelPreparationResult(
                task="pcs",
                family=self.settings.family,
                provider=self.settings.provider,
                model_name=self.settings.model_name,
                model_source=str(self.settings.model_path),
                download_root=(
                    str(self.settings.download_root) if self.settings.download_root else None
                ),
                local_files_only=True,
                ready=True,
                mode="local_path",
            )

        if self.settings.download_root is None:
            raise ValueError("PCS download_root must be configured for model preparation.")

        self.settings.download_root.mkdir(parents=True, exist_ok=True)
        file_infos = self._collect_file_infos()
        total_bytes = sum(file_info.file_size for file_info in file_infos)
        downloadable_infos = [
            file_info for file_info in file_infos if file_info.will_download or force_download
        ]
        bytes_to_download = sum(file_info.file_size for file_info in downloadable_infos)

        if not downloadable_infos and not force_download:
            self.console.print("[green]PCS model is already cached locally.[/green]")
            return ModelPreparationResult(
                task="pcs",
                family=self.settings.family,
                provider=self.settings.provider,
                model_name=self.settings.model_name,
                model_source=self.settings.model_name,
                download_root=str(self.settings.download_root),
                local_files_only=True,
                ready=True,
                downloaded_files=0,
                total_files=len(file_infos),
                downloaded_bytes=0,
                total_bytes=total_bytes,
                mode="cached",
            )

        self.console.print(
            "Preparing "
            f"[bold]{self.settings.family}[/bold] model "
            f"[bold]{self.settings.model_name}[/bold]"
        )
        self.console.print(f"Target cache: `{self.settings.download_root}`")
        self.console.print(
            f"{len(downloadable_infos)} file(s), {format_bytes(bytes_to_download)} to download."
        )

        progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(bar_width=32),
            console=self.console,
            transient=True,
        )

        with progress, suppress_hf_transfer_logs(), suppress_hf_progress_bars():
            overall_task = progress.add_task("Preparing files", total=len(downloadable_infos))
            current_task = progress.add_task("Waiting...", total=None)

            for index, file_info in enumerate(downloadable_infos, start=1):
                progress.update(
                    current_task,
                    description=(
                        f"[cyan]{index}/{len(downloadable_infos)}[/cyan] "
                        f"{file_info.filename} ({format_bytes(file_info.file_size)})"
                    ),
                    total=None,
                )
                hf_hub_download(
                    repo_id=self.repo_id,
                    filename=file_info.filename,
                    cache_dir=self.settings.download_root,
                    local_files_only=False,
                    force_download=force_download,
                )
                progress.advance(overall_task, 1)

            progress.update(
                current_task,
                description="[green]Download complete[/green]",
                total=1,
                completed=1,
            )

        return ModelPreparationResult(
            task="pcs",
            family=self.settings.family,
            provider=self.settings.provider,
            model_name=self.settings.model_name,
            model_source=self.settings.model_name,
            download_root=str(self.settings.download_root),
            local_files_only=True,
            ready=True,
            downloaded_files=len(downloadable_infos),
            total_files=len(file_infos),
            downloaded_bytes=bytes_to_download,
            total_bytes=total_bytes,
            mode="downloaded" if downloadable_infos else "cached",
        )
