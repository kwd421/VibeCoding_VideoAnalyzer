# VibeCoding_VideoAnalyzer v25 (Enterprise Grade Refactored)

## 1. 프로젝트 개요
- **목적**: AI 기반 고성능 VAD 무음 제거, CLIP 비전 챕터 분석 및 Whisper 자연어 대사 분석 스튜디오.
- **철학**: **"Zero-Disk I/O, Maximum RAM Throughput"**. 상용 소프트웨어 수준의 리소스 관리와 물리적 정합성 확보.
- **대상**: AMD Ryzen 7 8745HS (8코어/16쓰레드) 및 대용량 영상(12시간+) 처리 최적화.

## 2. 객체 지향 아키텍처 (System Architecture)

### [Core AI Engine] - `engine_core.py`
- **클래스**: `HyperTranscriptionEngine`
- **혁신 기술**:
    - **In-Memory Pipeline**: FFmpeg 파이프를 통해 오디오를 RAM으로 직접 추출. SSD 수명 보호 및 속도 폭발.
    - **Smart Chunking**: 10분 단위 지능형 분할 분석 + 자동 무음 절단점 탐색으로 대용량 영상 메모리 누수 원천 차단.
    - **CLIP Vision Analysis**: 영상 프레임을 분석하여 장면별 자동 챕터 분할 (Chatting, Game, Web 등).
    - **Z-Score Peak Detection**: 통계적 표준편차 기반의 초정밀 오디오 이상치 탐지.
    - **VAD Overlapping**: 청크 경계 2초 오버랩 적용으로 대사 잘림 방지.

### [Video Editor] - `video_editor.py`
- **클래스**: `VideoEditor`
- **핵심 최적화**:
    - **Dual Rendering Engine**: 
        - **Stream Copy (🚀 초고속)**: 인코딩 없이 데이터 복사로 수 초 내 렌더링 완료.
        - **Match Source (🎯 정밀)**: 원본 비트레이트/FPS를 완벽히 추종하는 프레임 단위 정밀 인코딩.
    - **FCP 7 XML Export**: 프리미어 프로, 다빈치 리졸브와 100% 호환되는 타임라인 데이터 생성.
    - **Command Length Fix**: `-filter_complex_script` 적용으로 수천 개의 컷도 오류 없이 처리.

### [UI & Workflow] - `gui_app.py`
- **클래스**: `CustomModelApp`
- **시니어 UI 로직**:
    - **Asynchronous UI Queue**: 모든 AI 연산을 메인 스레드와 분리하여 GUI 프리징(멈춤) 현상 완전 해결.
    - **3-Tier Saving System**: 분석 완료 후 [초고속 / 정밀 / XML] 목적별 저장 버튼 즉시 노출.
    - **Dynamic EMA ETA**: 지수 이동 평균(EMA) 기반 스마트 타이머로 정확한 남은 시간 안내 (시간 늘어남 현상 방지).
    - **VAD Parameter Control**: 무음 기준(초) 및 음성 패딩(초) 사용자 실시간 제어 UI.

## 3. 업데이트 연혁 (Today's Refactoring)
1. **[신규]** CLIP 기반 자동 챕터 분할 모드 추가.
2. **[신규]** 프리미어 프로용 타임라인 XML 내보내기 기능.
3. **[개선]** 모든 오디오 처리를 디스크에서 RAM(In-Memory)으로 전면 교체.
4. **[개선]** v9 동적 복잡도 예측 엔진 도입 (예상 용량 오차율 10% 미만).
5. **[삭제]** `video_settings_dialog.py` 폐기 및 메인 UI로 옵션 통합.
6. **[삭제]** SSD 임시 생성 파일(`*_temp.wav`) 완전 제거.

## 4. 개발 원칙 및 지침
- **Thread Safety**: UI 업데이트는 반드시 `ui_queue`를 통해서만 수행할 것.
- **Resource Guard**: 원본 품질을 초과하는 '뻥튀기 인코딩' 및 불필요한 연산 낭비를 시스템 수준에서 차단할 것.
- **Match Source**: 초벌 편집용 렌더링은 항상 원본의 해상도, 비트레이트, FPS를 보존하는 것을 원칙으로 함.

## 5. 실행 및 유지보수
- **진입점**: `python main.py`
- **의존성**: `transformers`, `pillow` (비전 분석용 추가), `faster-whisper`, `silero-vad`, `python-vlc`, `numpy`.
