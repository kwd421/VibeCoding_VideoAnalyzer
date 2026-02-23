# VAD AI Studio v21 (Refactored & Silence Editor Master)

## 1. 프로젝트 개요
- **목적**: 초고속 VAD(Voice Activity Detection) 기반 무음 제거 및 자연어 대사 분석 전문 스튜디오.
- **현재 버전**: v21 (Stability & Review Mode).
- **구조**: 기능별 모듈화 (Engine, Editor, Player, GUI)를 통한 유지보수 최적화.

## 2. 모듈 구성 (System Architecture)
- **`main.py`**: 프로그램 진입점 및 환경 정리.
- **`gui_app.py`**: 모든 UI 인터페이스 및 워크플로우 제어.
- **`engine_core.py`**: AI 분석 엔진 (Whisper v3 Turbo, Silero VAD, Numpy Peak Detection).
- **`video_editor.py`**: FFmpeg 기반 고속 인코딩 및 무음 제거 엔진 (ETA 및 진행률 지원).
- **`video_player.py`**: VLC 기반 비디오 재생 엔진 (실시간 자막 로드 지원).

## 3. 핵심 기능 로직
- **Smart Silence Removal (VAD)**: 
    - Silero VAD (Threshold 0.35) 기반 정밀 음성 감지.
    - 0.6초 이내 무음 자동 병합 및 0.25초 앞뒤 패딩으로 자연스러운 컷 연결.
- **Review & Preview Mode**:
    - 인코딩 전 음성 구간 리스트(시작/종료) 제공.
    - 리스트 우클릭으로 시작/종료 지점 즉시 이동 및 검토 가능.
- **Real-time Subtitle Preview**:
    - 자연어 분석 완료 즉시 임시 SRT를 생성하여 인코딩 없이 영상에 자막 적용.
- **Extreme Peak Detection**: 
    - Numpy 벡터 연산으로 초고속 하이라이트(깜놀) 구간 탐색.
- **Encoding Engine**:
    - AMD Ryzen 7 8745HS (8쓰레드) 최적화 인코딩.
    - 실시간 진행률(%) 및 예상 남은 시간(ETA) 표시.

## 4. 사용자 가이드
- **실행**: `python main.py`
- **단축키**: Space(재생/정지), Left/Right(5초 이동).
- **우클릭 메뉴**: 리스트 항목 우클릭 시 구간 시작/종료 지점으로 점프 가능.
- **의존성**: `torch`, `faster-whisper`, `silero-vad`, `python-vlc`, `imageio-ffmpeg`, `numpy`.
