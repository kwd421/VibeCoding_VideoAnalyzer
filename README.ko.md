# VibeCoding Video Analyzer

[English README](README.md)

> 개발 백업용 저장소입니다. 아직 바로 설치해서 쓰는 공개 배포판은 아닙니다.

로컬 영상 전사, 자막 타이밍 편집, 영상 위 자막 미리보기, 자막/타임라인 내보내기를 위한 데스크톱 앱입니다.

현재 프로젝트는 기존 영상 분석 워크플로를 Python/Tk 기반 macOS 개발 흐름에 맞춰 정리한 상태입니다. 분석은 가능한 한 로컬에서 처리하고, 사용자가 에디터에서 보는 자막 시간과 실제 미리보기/내보내기 시간이 최대한 동일하게 이어지도록 맞추는 것을 핵심 목표로 둡니다.

## 미리보기

[![VibeCoding Video Analyzer 미리보기](https://img.youtube.com/vi/QM7P5UEvVbk/maxresdefault.jpg)](https://www.youtube.com/watch?v=QM7P5UEvVbk)

[유튜브에서 미리보기 보기](https://www.youtube.com/watch?v=QM7P5UEvVbk)

## 현재 상태

- 개발 브랜치: `mac-experiment`
- 실행 진입점: `main.py`
- 자막 미리보기: 영상 위에 직접 표시되는 라이브 자막
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
- 자막을 영상에 입혀서 렌더링할 수 있습니다.

## 실행 요구사항

- 현재 주 개발 대상은 macOS입니다.
- Python이 필요합니다. `.venv/` 가상환경은 개발용으로 권장되지만, GitHub에서 내려받아야 하는 앱 파일은 아닙니다.
- 내장 영상 미리보기를 위해 VLC와 Python `vlc` 패키지가 필요합니다.
- 영상 처리와 렌더링에는 프로젝트 런타임 의존성의 FFmpeg 경로가 필요합니다.
- 로컬 모델 경로를 사용할 경우 `models/` 아래에 모델 파일이 있어야 합니다.
- WhisperX, Demucs, MLX, CoreML/whisper.cpp, 디노이즈, VAD 관련 패키지는 해당 옵션을 켤 때만 필요합니다.

현재는 GitHub에서 저장소만 받는다고 바로 실행되는 상태는 아닙니다. 소스코드는 GitHub에 있지만, 런타임 의존성, 로컬 모델 파일, Python 실행 환경은 별도로 준비해야 합니다. “다운로드 후 바로 실행”을 목표로 한다면 Python 환경을 요구하지 않는 패키징된 앱/빌드 산출물이 필요합니다.

## 실행 방법

이미 준비된 `.venv/` 가 있다면:

```bash
./run.command
```

다른 Python 환경에 의존성이 설치되어 있다면:

```bash
python main.py
```
