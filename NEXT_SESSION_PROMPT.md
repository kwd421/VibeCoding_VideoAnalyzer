아래 지시사항으로 이 프로젝트 작업을 이어가라.

작업 경로:
`C:\Users\Fleurdelys\Projects\VibeCoding_VideoAnalyzer`

반드시 먼저 읽을 문서:
- `AGENTS.md`
- `CODEX.md`
- `HANDOFF.md`
- `STATUS_CURRENT.md`

현재 전제:
- 이 프로젝트는 복구 + 부분 리팩터링 이후의 혼합 상태다.
- `gui_app.py`는 다시 실행 가능한 상태로 돌아왔지만, 실제 런타임 한국어 UI는 아직 완전히 정상화됐다고 보면 안 된다.
- 일부 source 문자열은 괜찮아 보여도, 실제 widget text 값은 여전히 깨져 있을 수 있다.

이번 세션의 최우선 목표:
1. 새 기능 추가를 멈추고
2. `gui_app.py`의 실제 런타임 한국어 UI를 다시 검증하고
3. 깨진 한국어 UI를 실제 widget text 기준으로 복구한 뒤
4. overlay 최소 경로를 다시 확인하고
5. 그 다음에만 preview/selection 관련 버그를 고쳐라.

중요 규칙:
- source search만으로 한국어 UI가 복구됐다고 판단하지 마라.
- 반드시 실제 widget text 값을 확인하라.
- 기능 수정과 한국어 문자열 수정을 같은 턴에 섞지 않는 것이 기본이다.
- `gui_app.py` 같은 큰 파일에는 line-range overwrite를 쓰지 마라.
- shell에서 한글 literal을 직접 inline replace하지 마라.

현재 가장 중요한 실제 버그 우선순위:
1. `ImageOverlay` rotation이 실제 화면에서 여전히 잘못 보이는 문제
2. preview에서 image overlay를 선택한 뒤 바깥 클릭 시 image가 사라지거나 desync되는 문제
3. 여러 image overlay의 layer ordering이 신뢰할 수 없다는 문제
4. preview 선택 경로와 timeline 선택 경로에 따라 바깥 클릭 결과가 달라지는 문제

하지만 이 버그들을 바로 고치기 전에 먼저 해야 할 일:
1. `py_compile`
2. `import`
3. `CustomModelApp(...)` create
4. 실제 widget text 확인:
   - 탭 이름
   - 분석 시작 / 작업 중지 버튼
   - 오버레이 타임라인 주변 UI
   - 오버레이 속성 패널 라벨
   - 상태 문구
5. 최소 overlay 경로 확인:
   - ImageOverlay preview
   - TextOverlay preview
   - Overlay Timeline
   - export collection

보고 형식:
[1] 이번 세션 범위
[2] 실제로 확인한 런타임 한국어 UI 상태
[3] 최소 overlay 경로 검증 결과
[4] 수정한 파일
[5] 수정한 이유
[6] 실제 검증 결과
[7] 아직 남는 위험

중요:
- “코드상 그럴 것 같다”가 아니라 실제 런타임 기준으로 검증하라.
- 실제 widget text가 아직 깨져 있으면, 기능 작업보다 그 복구가 먼저다.
- 최소 경로가 다시 확인되기 전에는 더 깊은 기능 추가나 리팩터링을 진행하지 마라.
