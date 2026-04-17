from __future__ import annotations

import logging
from functools import lru_cache

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile

from core.audio import ensure_wav_filename
from services.bootstrap import AppContext, build_app_context

logger = logging.getLogger(__name__)
UPLOAD_FILE = File(...)

app = FastAPI(title="iVoice API", version="0.1.0")


@lru_cache(maxsize=1)
def get_context() -> AppContext:
    return build_app_context()


@app.get("/health")
def health() -> dict[str, str]:
    context = get_context()
    return {
        "status": "ok",
        "app_name": context.settings.app_name,
        "asr_family": context.service.asr_engine.family_name,
        "asr_provider": context.service.asr_engine.provider_name,
        "translation_family": context.service.translation_engine.family_name,
        "translation_provider": context.service.translation_engine.provider_name,
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
