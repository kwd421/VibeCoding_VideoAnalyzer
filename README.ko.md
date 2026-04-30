# VibeCoding Video Analyzer

로컬 영상 전사, 자막 타이밍 편집, 영상 위 자막 미리보기, 자막/타임라인 내보내기를 위한 데스크톱 앱입니다.

현재 프로젝트는 기존 영상 분석 워크플로를 Python/Tk 기반 macOS 개발 흐름에 맞춰 정리한 상태입니다. 분석은 가능한 한 로컬에서 처리하고, 사용자가 에디터에서 보는 자막 시간과 실제 미리보기/내보내기 시간이 최대한 동일하게 이어지도록 맞추는 것을 핵심 목표로 둡니다.

[English README](README.md)

## 현재 상태

- 개발 브랜치: `mac-experiment`
- 실행 진입점: `main.py`
- 현재 구조: 주요 기능을 `app/` 패키지 하위로 분리
- 자막 미리보기: 임시 ASS 파일 대신 정규화된 subtitle cue 기반 라이브 오버레이
- 내보내기: 자막 포맷, FCPXML, 영상 렌더/자막 번인 지원
- 실험 옵션: WhisperX 정렬, Demucs 보컬 분리, Gemma 4 MLX 이상 세그먼트 필터

## 주요 기능

- 로컬 영상 파일을 불러와 음성 분석을 실행합니다.
- Faster-Whisper 계열 경로와 설정된 경우 CoreML/whisper.cpp 워커 경로를 사용합니다.
- 외부 VAD, 디노이즈, Demucs 배경음/보컬 분리, WhisperX forced alignment 옵션을 제공합니다.
- Gemma 4 MLX를 이용해 의심스러운 짧은 세그먼트나 환각성 문장을 검토하는 실험 기능이 있습니다.
- 자막 행, 시작/종료 시간, 단어 블록을 편집할 수 있습니다.
- 마우스 휠 기반 싱크 조정과 인접 자막 경계 동시 이동을 지원합니다.
- 영상 위에 직접 자막 오버레이를 띄워 미리볼 수 있습니다.
- `SRT`, `VTT`, `TXT`, `CSV`, `FCPXML` 형식으로 내보낼 수 있습니다.
- FFmpeg drawtext 필터를 생성해 자막 번인 렌더링을 수행할 수 있습니다.

## 프로젝트 구조

```text
.
├── main.py                         # 앱 실행 진입점
├── run.command                     # macOS용 실행 스크립트
├── app/
│   ├── ui/                         # Tk UI, 단어 편집기, 비디오 플레이어 오버레이
│   ├── engine/                     # 분석 컨트롤러, 핵심 파이프라인, 오디오/비전 처리
│   ├── core/                       # 설정, 타임라인, 자막 cue, 텍스트 유틸리티
│   └── media/                      # 영상 렌더링, XML/export 도우미
├── tools/                          # CoreML 전사 워커 등 보조 스크립트
├── tests/                          # 타이밍, 분할, cue 회귀 테스트
├── docs/                           # 설계 메모와 구현 계획
├── DEPLOYMENT.md                   # 패키징 메모
├── HANDOFF.md                      # 프로젝트 인수인계/현황 메모
└── VibeAnalyzer.spec               # Windows 빌드 흐름에서 쓰는 PyInstaller spec
```

## 실행 요구사항

- 현재 주 개발 대상은 macOS입니다.
- 프로젝트 루트에 `.venv/` 가 필요합니다.
- 내장 영상 미리보기를 위해 VLC와 Python `vlc` 패키지가 필요합니다.
- 영상 처리와 렌더링에는 프로젝트 런타임 의존성의 FFmpeg 경로가 필요합니다.
- 로컬 모델 경로를 사용할 경우 `models/` 아래에 모델 파일이 있어야 합니다.
- WhisperX, Demucs, MLX, CoreML/whisper.cpp, 디노이즈, VAD 관련 패키지는 해당 옵션을 켤 때만 필요합니다.

현재 저장소에는 완전한 dependency lockfile이 없으므로, 당장의 개발 기준은 로컬 `.venv` 환경입니다.

## 실행 방법

```bash
./run.command
```

또는:

```bash
source .venv/bin/activate
python main.py
```

## 테스트

```bash
PYTHONPATH=$PWD .venv/bin/python -m unittest tests.test_timing_and_split_rules
```

컴파일/임포트 확인용 스모크 테스트:

```bash
PYTHONPATH=$PWD .venv/bin/python -m py_compile \
  main.py \
  tools/coreml_transcribe_worker.py \
  app/ui/gui_app.py \
  app/ui/ui_block_editor.py \
  app/ui/video_player.py \
  app/engine/engine_core.py \
  app/engine/analysis_controller.py \
  app/engine/audio_processor.py \
  app/engine/vision_processor.py \
  app/core/config_models.py \
  app/core/subtitle_cues.py \
  app/core/timeline_manager.py \
  app/core/text_sanitizer.py \
  app/core/event_dispatcher.py \
  app/core/transcription_backends.py \
  app/media/video_editor.py
```

## 개발 메모

- 실행 중 생성되는 미디어, 프리뷰 파일, 모델 가중치, 백업 파일은 git에 올리지 않습니다.
- 에디터에서 보이는 자막 시간이 미리보기와 내보내기의 기준입니다.
- 라이브 미리보기 경로에 임시 ASS 파일 의존성을 다시 넣지 않는 것을 원칙으로 합니다.
- 실험 기능은 명시적으로 켰을 때만 동작해야 하며, 실패를 엉뚱한 fallback으로 숨기지 않아야 합니다.
- 코드 이동 시 `app.*` 패키지 import를 유지해 패키징과 워커 스크립트가 예측 가능하게 동작하도록 합니다.
