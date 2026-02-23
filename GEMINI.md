# VibeCoding_VideoAnalyzer v21 (Refactored & Object-Oriented Master)

## 1. 프로젝트 개요
- **목적**: AI 기반 고성능 VAD(Voice Activity Detection) 무음 제거 및 Whisper 자연어 대사 분석 스튜디오.
- **철학**: 기능별 완전 객체화(Modular OOD)를 통한 유지보수성 극대화 및 하드웨어 가속 최적화.
- **대상**: AMD Ryzen 7 8745HS (8코어/16쓰레드) 환경에 최적화됨.

## 2. 객체 지향 아키텍처 (System Architecture)

### [Core Engine] - `engine_core.py`
- **클래스**: `HyperTranscriptionEngine`
- **역할**: AI 모델 관리 및 분석 연산 담당.
- **핵심 기술**:
    - **Whisper v3 Turbo**: 대사 추출 (int8 양자화 적용).
    - **Silero VAD**: 초고속 음성 구간 감지 (Threshold 0.35, Sensitivity 상향).
    - **Numpy Vectorization**: 초고속 깜놀(Peak) 구간 탐색 로직.

### [Video Player] - `video_player.py`
- **클래스**: `VideoPlayer`
- **역할**: VLC 엔진을 캡슐화하여 영상 재생 및 사용자 인터랙션 처리.
- **주요 기능**: 외부 SRT 자막 실시간 로드, 구간 탐색(Seek), 재생 상태 관리.

### [Video Editor] - `video_editor.py`
- **클래스**: `VideoEditor`
- **역할**: FFmpeg 명령어를 생성하고 실행하여 물리적 편집 수행.
- **최적화**:
    - **Smart Merging**: 2.0초 미만 무음 자동 병합으로 자연스러운 호흡 유지.
    - **Progress Parsing**: FFmpeg 로그 실시간 파싱을 통한 정확한 진행률(%) 및 ETA(남은 시간) 계산.

### [UI Orchestrator] - `gui_app.py`
- **클래스**: `CustomModelApp`
- **역할**: 각 엔진 객체를 생성/연동하고 전체 워크플로우 제어.
- **핵심 UI 로직**:
    - **Dynamic Action Button**: 상태에 따라 "분석 시작" -> "무음 제거 영상 저장"으로 자동 전환.
    - **Smart Column Navigation**: 리스트의 '시작' 또는 '종료' 컬럼 클릭 시 해당 지점으로 즉시 이동.

## 3. 필수 핵심 기능 (Core Features)
1. **Seamless VAD Review**: 분석 완료 즉시 음성 구간 리스트를 제공하며, 인코딩 없이 즉시 구간 검토 가능.
2. **Real-time Subtitle Overlay**: 자연어 분석 직후 임시 SRT를 생성하여 영상 플레이어에 실시간 적용.
3. **Dynamic Interaction**: 영상 화면 클릭만으로 재생/일시정지 토글 지원.
4. **Adaptive Processing**: 작업 중지 버튼을 통한 즉각적인 FFmpeg 및 AI 프로세스 강제 종료 지원.
5. **HW Optimization**: 모든 인코딩 및 분석 단계에서 8쓰레드 강제 할당으로 하드웨어 성능 풀가동.

## 4. 개발 원칙 및 지침 (Mandatory Principles)
- **Strict Object-Oriented Design (OOD)**: 모든 신규 기능 추가 및 수정 시 반드시 객체 지향 구조를 유지해야 함.
    - **핵심 로직 분리**: GUI 클래스(`CustomModelApp`)에 비즈니스 로직을 직접 구현하는 것을 금지함. 반드시 전용 엔진(`Engine`, `Editor`, `Player`) 클래스 내에 캡슐화해야 함.
    - **단일 책임 원칙 (SRP)**: 한 모듈은 하나의 역할(분석, 편집, 재생, UI 제어)만 수행해야 함.
    - **모듈화**: 신규 엔진이 필요한 경우(예: 얼굴 인식, 자막 번역 등) 반드시 별도의 `.py` 파일과 클래스로 분리하여 기존 구조에 주입하는 방식을 취함.

## 5. 실행 및 유지보수
- **진입점**: `python main.py`
- **의존성**: `torch`, `faster-whisper`, `silero-vad`, `python-vlc`, `imageio-ffmpeg`, `numpy`.
- **정리**: `.gitignore`를 통해 `deprecated/`, `__pycache__`, 임시 미디어 파일(`*.wav`, `*.srt`) 제외 완료.
