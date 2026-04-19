from __future__ import annotations

import json
from pathlib import Path

from schemas.command import CommandNormalizationResult
from schemas.command_run import CommandArtifacts, CommandMetadata, CommandRun


class RunArtifactStore:
    def build_artifacts(
        self,
        *,
        run_dir: str | Path,
        audio_path: str | Path,
    ) -> CommandArtifacts:
        return CommandArtifacts.from_run_dir(
            run_dir,
            audio_path=audio_path,
        )

    def load_metadata(self, run_dir: str | Path) -> CommandMetadata:
        artifacts = self.build_artifacts(run_dir=run_dir, audio_path="")
        metadata_path = Path(artifacts.metadata_path)
        if not metadata_path.exists():
            raise FileNotFoundError(f"Run metadata not found: {metadata_path}")
        return CommandMetadata.model_validate(json.loads(metadata_path.read_text(encoding="utf-8")))

    def write_command_artifacts(
        self,
        *,
        artifacts: CommandArtifacts,
        source_text: str,
        normalized_text: str,
        normalization_result: CommandNormalizationResult,
    ) -> None:
        self._ensure_run_dir(artifacts)
        Path(artifacts.source_path).write_text(source_text + "\n", encoding="utf-8")
        Path(artifacts.command_en_path).write_text(normalized_text + "\n", encoding="utf-8")
        Path(artifacts.normalization_spans_path).write_text(
            json.dumps(
                [span.model_dump(mode="json") for span in normalization_result.spans],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def write_metadata(self, artifacts: CommandArtifacts, metadata: CommandMetadata) -> None:
        self._ensure_run_dir(artifacts)
        Path(artifacts.metadata_path).write_text(
            json.dumps(metadata.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def build_run(self, artifacts: CommandArtifacts, metadata: CommandMetadata) -> CommandRun:
        return CommandRun(
            artifacts=artifacts,
            metadata=metadata,
        )

    def _ensure_run_dir(self, artifacts: CommandArtifacts) -> None:
        Path(artifacts.run_dir).mkdir(parents=True, exist_ok=True)
