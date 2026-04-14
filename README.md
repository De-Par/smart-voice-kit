<div align="center">

# Smart Voice Kit

**Offline-first voice toolkit for smart-device and local assistant prototypes**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge)](https://www.python.org/)
[![faster-whisper](https://img.shields.io/badge/faster--whisper-ASR-16A34A?style=for-the-badge)](https://github.com/SYSTRAN/faster-whisper)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-61718B?style=for-the-badge)](#requirements)
<br />

[![PySide6](https://img.shields.io/badge/PySide6-Desktop_UI-242378?style=for-the-badge)](https://doc.qt.io/qtforpython-6/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Web_UI-FF4B4B?style=for-the-badge)](https://docs.streamlit.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-HTTP_API-0F766E?style=for-the-badge)](https://fastapi.tiangolo.com/)
[![Uvicorn](https://img.shields.io/badge/Uvicorn-ASGI_Server-9535E9?style=for-the-badge)](https://www.uvicorn.org/)

`record -> save wav -> transcribe -> show text -> save metadata`

Built for [Yandex Education Studcamp](https://education.yandex.ru/studcamp-mipt-cshse)

</div>

<p align="center">
    <img src="https://raw.githubusercontent.com/De-Par/smart-voice-kit/main/assets/images/demo.png" alt="app screenshot" width="50%">
</p>

Smart Voice Kit is a clean local foundation for voice UX experiments: desktop capture, offline-capable ASR, structured artifacts, and a codebase that can grow into style-aware speech control and TTS without throwing the architecture away.

## Overview

- local ASR via `faster-whisper`
- desktop UI via `PySide6`
- browser UI via `Streamlit`
- CLI via `Typer + Rich`
- HTTP API via `FastAPI`
- unified service layer shared by all clients
- offline-first runtime with explicit model preparation

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
voice-cli prepare-asr
voice-desktop
```

## Feature Map

| Area | What is available now |
| --- | --- |
| Audio capture | Desktop recording and WAV ingestion |
| ASR | Local transcription via `faster-whisper` |
| Clients | Desktop UI, Streamlit UI, CLI, FastAPI |
| Storage | Run-based local artifacts in `runs/` |
| Configuration | TOML config via `config.toml` |
| Extensibility | Reserved interfaces for style parsing and TTS |

## Architecture

| Layer | Responsibility |
| --- | --- |
| `app/ui_desktop/` | Primary local desktop client |
| `app/ui_streamlit/` | Secondary browser client |
| `app/tui/` | CLI commands |
| `app/api/` | HTTP API |
| `core/audio/` | WAV I/O and audio utilities |
| `core/asr/` | ASR interfaces and backends |
| `core/style/` | Style parsing extension point |
| `core/tts/` | TTS extension point |
| `services/` | Orchestration and artifact persistence |
| `schemas/` | Pydantic models and structured results |

Key design rules:

- all clients call the same business logic
- backend-specific code is isolated behind interfaces
- operations return structured models instead of ad-hoc prints
- future style and TTS work can be added without reshaping the whole app

## Requirements

- Python 3.11+
- macOS or Linux
- `ffmpeg` is recommended for `faster-whisper`

## Installation

Minimal install:

```bash
pip install -e .
```

Install with development tools:

```bash
pip install -e ".[dev]"
```

Runtime parameters live in [config.toml](/Users/Mand/Desktop/TTS/config.toml:1).

## Offline-first ASR

By default the runtime uses `local_files_only = true`, so regular transcription does not need network access after the model is prepared once.

Prepare the local cache:

```bash
voice-cli prepare-asr
```

Force a redownload:

```bash
voice-cli prepare-asr --force
```

If you want fully explicit local model resolution, set `asr.model_path` to a converted local `faster-whisper` model directory.

## Running

Desktop UI:

```bash
voice-desktop
```

Streamlit UI:

```bash
streamlit run app/ui_streamlit/main.py
```

CLI:

```bash
voice-cli prepare-asr
voice-cli transcribe-file samples/example.wav
voice-cli transcribe-last
```

API:

```bash
voice-api
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/transcribe/file -F "file=@samples/example.wav"
```

## Metadata Schema

`metadata.json` includes:

- `id`
- `timestamp`
- `duration_seconds`
- `sample_rate`
- `audio_path`
- `language`
- `transcript`
- `inference_seconds`
- `asr_backend`
- `model_name`

## Repository Layout

```text
app/
  api/
  tui/
  ui_desktop/
  ui_streamlit/
core/
  audio/
  asr/
  style/
  tts/
services/
schemas/
runs/
data/
samples/
```

## Development

```bash
ruff check .
ruff format .
```

## Roadmap

- style-aware prompt parsing for speech control
- local TTS backends behind a shared interface
- richer audio preprocessing hooks
- more device-oriented runtime flows beyond plain WAV transcription

## Notes

- the current runtime supports WAV input only
- `maybe_normalize_audio()` is intentionally a no-op for now
- style parsing and TTS are reserved in the architecture, but not active in runtime yet
