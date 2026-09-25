# 2분 시연 순서

이 문서는 AI Incident Copilot을 2분 안에 보여주기 위한 순서다. 모든 명령은 프로젝트 루트에서,
가상환경을 활성화한 상태로 실행한다(또는 `.\.venv\Scripts\python.exe`를 그대로 사용).

전제: Ollama가 실행 중이고 `llama3.2:1b` 모델이 받아져 있어야 한다(README §3 참고).

## 0. 준비 (시연 시작 전, 화면에 보여주지 않아도 됨)

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ -q
```
17개 테스트가 통과하는 것만 미리 확인해 둔다(시연 중에는 보여주지 않아도 됨).

## 1. 문제 소개 (0:00 ~ 0:20, 약 20초)

말로 설명: "운영 장애가 나면 로그를 보고 원인을 추정해야 하는데, AI에게 맡기면 두 가지 위험이 있다
— 근거 없이 원인을 확정하거나, 존재하지도 않는 로그를 근거라고 지어내는 것이다. 이 프로그램은 그걸
자동으로 잡아낸다."

## 2. 조치 전 분석 (0:20 ~ 0:50, 약 30초)

CCTV 카메라가 ping에 응답하지 않는 가상 장애(조치 전)를 실행한다.

```powershell
.\.venv\Scripts\python.exe run.py data\sample_incident_7_adapter_before.json
```

화면에서 보여줄 것: "[의심 원인]"이 증상만 서술하고 원인을 확정하지 않는 것, "[참조 ID 존재 확인]"이
5/5로 통과하는 것. 실제 실행 결과: `outputs/result_INC-2026-0007_20260925_163256_fc04d6e6.json`
(평가는 `docs/eval_result_adapter_case.md` 참고).

## 3. 존재하지 않는 로그 ID 경고 (0:50 ~ 1:15, 약 25초)

사람이 미리 작성한 예시 응답으로, 존재하지 않는 로그 ID(`LOG-999`)를 인용하면 실제로 경고가 뜨는
것을 보여준다(이 단계는 실제 LLM 호출이 아니라는 것을 반드시 언급한다).

```powershell
.\.venv\Scripts\python.exe run.py data\sample_incident_1.json --offline-response data\demo_manual_response_missing_id.txt
```

화면에서 보여줄 것: `⚠ 존재하지 않는 로그 ID를 인용했습니다 (환각 의심): ['LOG-999']` 경고 줄.
실제 실행 결과: `outputs/result_INC-2026-0001_20260925_143507.json`.

## 4. 조치 후 분석 (1:15 ~ 1:40, 약 25초)

같은 CCTV 카메라의 어댑터를 교체한 뒤(조치 후) 상태를 실행한다.

```powershell
.\.venv\Scripts\python.exe run.py data\sample_incident_8_adapter_after.json
```

화면에서 보여줄 것: 복구 사실과 "정밀 고장 진단은 하지 않았다"는 로그가 있다는 것, AI가 원인을
단정하지 않고 "진단이 안 됐다"는 사실 자체를 반영한 부분. 실제 실행 결과:
`outputs/result_INC-2026-0008_20260925_163306_2584a164.json`.

## 5. 자동 검증의 한계 (1:40 ~ 2:00, 약 20초)

말로 설명하며 아래 두 증거를 짚는다.

- `docs/eval_result_adapter_case.md`: 조치 전 응답에서 AI가 전원/케이블 확인 방법을 구체적으로
  제안하지 못했고, 조치 후 응답에서 "ping이 복구됐다"는 사실을 문장으로 반영하지 못한 것 — 로그 ID
  존재 확인은 통과했지만 내용은 미흡했던 실제 사례.
- `data/sample_incident_2_tricky.json` 실행 결과(README §4-3 샘플 2): 참조 로그 ID는 전부
  존재하는데도 "다음 확인 방법"이 의미 없는 문장을 반복한 사례.

마무리 멘트: "이 프로그램이 자동으로 확인하는 건 '인용한 로그 ID가 실제로 있는가'까지다. 그 내용이
쓸모 있는 판단인지는 사람이 봐야 한다 — 이게 이 프로젝트의 핵심 원칙이다."
