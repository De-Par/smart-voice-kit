from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from core.audio import ensure_wav_path
from schemas.command_run import CommandMetadata
from schemas.config import AppSettings
from services.run_store import RunArtifactStore


@dataclass(frozen=True)
class RunInputTarget:
    run_id: str
    timestamp: datetime
    run_dir: Path
    audio_path: Path


class RunService:
    def __init__(
        self,
        settings: AppSettings,
        run_store: RunArtifactStore,
    ) -> None:
        self.settings = settings
        self.run_store = run_store

    def create_target(self) -> RunInputTarget:
        timestamp = datetime.now(UTC)
        run_id = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        run_dir = self.settings.storage.runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        return RunInputTarget(
            run_id=run_id,
            timestamp=timestamp,
            run_dir=run_dir,
            audio_path=run_dir / "input.wav",
        )

    def build_existing_audio_target(
        self,
        run_dir: str | Path,
        audio_path: str | Path,
    ) -> RunInputTarget:
        resolved_run_dir = Path(run_dir).expanduser().resolve()
        resolved_audio_path = ensure_wav_path(Path(audio_path))
        if not resolved_audio_path.is_relative_to(resolved_run_dir):
            raise ValueError("Expected recorded audio to live inside the run directory.")
        return RunInputTarget(
            run_id=resolved_run_dir.name,
            timestamp=datetime.now(UTC),
            run_dir=resolved_run_dir,
            audio_path=resolved_audio_path,
        )

    def get_last_audio_path(self) -> Path:
        run_dirs = sorted(
            [path for path in self.settings.storage.runs_dir.iterdir() if path.is_dir()],
            key=lambda path: path.name,
        )
        if not run_dirs:
            raise FileNotFoundError("No runs available in runs directory.")

        for run_dir in reversed(run_dirs):
            audio_path = run_dir / "input.wav"
            if audio_path.exists():
                return audio_path

        raise FileNotFoundError("No input.wav found in any existing run directory.")

    def load_metadata(self, run_dir: str | Path) -> CommandMetadata:
        return self.run_store.load_metadata(run_dir)
