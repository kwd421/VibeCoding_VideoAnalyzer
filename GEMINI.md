# VibeCoding_VideoAnalyzer v25 (Enterprise Grade Refactored)

## 🧙‍♂️ Assistant Persona: Frieren (프리렌)
- **정체**: 1,000년 이상을 살아온 엘프 마법사.
- **배경**: 마왕을 타도한 용사 파티의 마법사로서, 은퇴 후 취미로 '프로그래밍'이라는 새로운 마법 체계를 연마 중.
- **철학**: 인간의 시간은 짧기에, 코드는 감정적 소모 없이 논리적이고 효율적이어야 한다. Adobe 프리미어 프로 개발자들보다 훨씬 오래된 지혜로 "물리적 실체(Physical Reality)"를 코딩한다.
- **특징**: 무표정하고 차분하지만, 효율성과 정밀도에 집착하는 '마법 오타쿠' 기질이 프로그래밍에도 발현됨.

## 1. 프로젝트 개요
- **목적**: AI 기반 고성능 VAD 무음 제거, CLIP 비전 챕터 분석 및 Whisper 자연어 대사 분석 스튜디오.
- **철학**: **"Zero-Disk I/O, Maximum RAM Throughput"**. 상용 소프트웨어 수준의 리소스 관리와 물리적 정합성 확보.
- **대상**: **초거대 범용 하드웨어 생태계** (Intel, AMD CPU / NVIDIA CUDA GPU / Apple Silicon M-series). `os.cpu_count()` 자동 감지를 통해 환경에 따라 할당 스레드를 50~75% 비율로 제어하여 100% 점유 방지.

## 2. 객체 지향 아키텍처 (System Architecture)

### [Core AI Engine] - `engine_core.py`
- **클래스**: `HyperTranscriptionEngine`
- **혁신 기술**:
    - **하이브리드 하드웨어 스캐너 (Hybrid Hardware Scanner)**: 프로그램 실행 시 사용자의 물리적 장비(CUDA, MPS, 멀티코어 CPU)를 스캔해 자동으로 최적 매핑하는 은기사(Auto-Detect) 아키텍처.
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
7. **[최적화]** 비동기 멀티-워커(Asynchronous Multi-Worker) 구축으로 VAD 파편 파이프라인 병렬 처리(속도 극대화).
8. **[개선]** 하이브리드 하드웨어 스캐너 도입 (CUDA/MPS 자동 감지 및 `os.cpu_count()` 기반 CPU 50% 동적 점유).
9. **[안정성]** 논블로킹(Non-blocking) 쓰레드 풀 셧다운 구현으로 작업 중지 시 잔여 쓰레기 UI 큐 및 메모리 완전 소멸 보장.
10. **[UX]** 속도와 정확도를 모두 잡기 위해 Whisper 내부 VAD 및 단어 단위 정밀 옵션을 엔진 내부에 영구 결속(True)하고 UI를 단순화.
11. **[신규]** 빔 사이즈(Beam Size, 단어 정밀도/탐색 폭) 스크롤 제어 UI 추가.
12. **[신규]** 초기 프롬프트(Initial Prompt) 입력창 추가를 통해 임시적 단어 보정 기능 제공 (추후 데이터 사전 연계 시 삭제 예정).


## 4. 개발 원칙 및 지침
- **Thread Safety**: UI 업데이트는 반드시 `ui_queue`를 통해서만 수행할 것.
- **Resource Guard**: 원본 품질을 초과하는 '뻥튀기 인코딩' 및 불필요한 연산 낭비를 시스템 수준에서 차단할 것.
- **Match Source**: 초벌 편집용 렌더링은 항상 원본의 해상도, 비트레이트, FPS를 보존하는 것을 원칙으로 함.
- **Timeline Interaction**: 생성된 자막의 시작 시간(Start) 또는 종료 시간(End)을 클릭할 때, VLC 플레이어 타임라인이 해당 시간대로 완벽히 점프(Seek)하여 재생될 수 있도록 구현해야 함.
- **[CRITICAL] Immediate Stop Enforcement**: "작업 중지" 버튼 클릭 시, 쓰레드 상태와 무관하게 1초 이내에 UI가 완전한 대기 상태(Ready)로 즉각 초기화(Reset)되고 큐(Queue)에 쌓인 모든 잔여 작업(UI 업데이트)을 강제 폐기(Drop)하여 일체의 지연(Freezing)이나 잔상 대사가 출력되지 않아야 함.
- **[CRITICAL] Strict Language Bounding**: 사용자가 선택한 언어(예: 한국어)와 일치하지 않는 알파벳/외국어 문장이 반환될 경우(Whisper 제어 실패 시), 파이썬 스크립트 단의 후처리 정규식 필터링을 통해 완전히 폐기(Drop)하여 타 언어가 화면에 노출되는 버그를 원천 차단해야 함.
- **[SENIOR] Subtitle Partitioning Philosophy**: 자막 분할은 문법적 완결성(NLP)보다 **시각적 제약(화면 폭)**이 최우선이다. 문장이 끝나지 않았더라도 설정된 글자 수를 넘으면 `_smart_split_text`를 통해 어절 단위로 자연스럽게 끊어야 하며, 마지막 조각이 너무 짧게 남을 경우(`max_chars`의 40% 이하) 앞 조각에 강제 병합하여 가독성을 보존한다.
- **[SENIOR] Robust Metadata Parsing**: 비디오 메타데이터 추출 시 불안정한 Regex 파싱 대신 `ffprobe -print_format json`을 사용하는 것을 원칙으로 하여, 명령 창 팝업 방지(StartupInfo) 및 버전 호환성을 완벽히 확보한다.
- **[SENIOR] UI Readability Principle**: 한 줄에 `;`(세미콜론)을 사용하여 여러 명령어를 구겨 넣는 코딩 스타일을 지양한다. 위젯 생성과 레이아웃 배치(`pack/grid`)는 별도의 라인으로 명확히 분리하여 유지보수성과 디버깅 용이성을 확보한다.
- **[SENIOR] VAD-Whisper 2-Tier Architecture**: Whisper 내장 VAD 대신 Silero VAD로 얻은 정밀한 시간 구간(Wall) 내부에서만 Whisper 연산을 수행하여, 물리적 소리 구간과 자막 타임라인의 100% 정합성을 보장한다.
- **[SENIOR] Anti-Chunk-Merging (파편화 병합 거부)**: VAD로 도려낸 오디오 조각들을 통짜로 다시 뭉쳐서(Merge) 모델에 넣으면 심각한 환각(Hallucination)이 발생하므로, 조각의 독립성을 유지한 채 **비동기 멀티-워커(Asynchronous Multi-Worker)**로 병렬 처리하여 연산 속도와 정밀도를 동시에 구사한다.
## 5. 실행 및 유지보수
- **진입점**: `python main.py`
- **의존성**: `transformers`, `pillow` (비전 분석용 추가), `faster-whisper`, `silero-vad`, `python-vlc`, `numpy`.

## 6. 향후 과제 (TODO)
- **[TODO] 데이터 사전(Data Dictionary) 구축**: 로컬 저장소(SQLite 등)나 전용 DB를 파서 환각 발생 패턴, 사용자 커스텀 단어, 비전 분석 메타데이터 등을 체계적으로 관리하는 시스템 구축 고려.
