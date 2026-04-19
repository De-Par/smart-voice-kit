from __future__ import annotations

import logging
from functools import lru_cache

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict

from core.audio import ensure_wav_filename
from services.bootstrap import AppContext, build_app_context

logger = logging.getLogger(__name__)
UPLOAD_FILE = File(...)

app = FastAPI(title="iVoice API", version="0.1.0")


class NormalizeTextRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    language: str | None = None


@lru_cache(maxsize=1)
def get_context() -> AppContext:
    return build_app_context()


@app.get("/health")
def health() -> dict[str, str]:
    context = get_context()
    translation = context.settings.translation
    pcs = context.settings.pcs
    return {
        "status": "ok",
        "app_name": context.settings.app_name,
        "asr_family": context.service.asr_engine.family_name,
        "asr_provider": context.service.asr_engine.provider_name,
        "translation_enabled": str(translation.enabled).lower(),
        "translation_family": translation.family,
        "translation_provider": translation.provider,
        "translation_target_language": translation.target_language,
        "pcs_enabled": str(pcs.enabled).lower(),
        "pcs_family": pcs.family,
        "pcs_provider": pcs.provider,
    }


@app.post("/transcribe/file")
async def transcribe_file(file: UploadFile = UPLOAD_FILE, language: str | None = None) -> dict:
    try:
        filename = ensure_wav_filename(file.filename or "input.wav")
        payload = await file.read()
        result = get_context().service.transcribe_bytes(
            payload,
            filename=filename,
            language=language,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - defensive API boundary
        logger.exception("API transcription failed for %s", filename)
        raise HTTPException(status_code=500, detail="Local transcription failed.") from error

    return result.model_dump(mode="json")


@app.post("/normalize/text")
def normalize_text(payload: NormalizeTextRequest) -> dict:
    try:
        result = get_context().service.normalize_text_input(
            payload.text,
            language=payload.language,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - defensive API boundary
        logger.exception("API text normalization failed")
        raise HTTPException(
            status_code=500, detail="Local command normalization failed."
        ) from error

    return result.model_dump(mode="json")


def run() -> None:
    context = get_context()
    uvicorn.run(
        "app.api.main:app",
        host=context.settings.api.host,
        port=context.settings.api.port,
        reload=False,
    )


if __name__ == "__main__":
    run()
