# 실행 증거 (evidence)

이 폴더의 JSON 파일들은 **실제 실행 결과의 사본**이며, 원본은 로컬 `outputs/`에 생성되었다
(`outputs/*.json`은 `.gitignore`에 의해 GitHub에 올라가지 않으므로, 심사자가 직접 열어볼 수
있도록 핵심 사례 4건만 골라 이 폴더에 그대로 복사해 두었다). 내용은 손대지 않았다 — 원본과
바이트 단위로 동일하다(`Compare-Object`로 확인).

| 파일 | 원본 (`outputs/`) | 어떤 실행인지 |
|---|---|---|
| `result_incident_1_normal.json` | `result_INC-2026-0001_20260925_143501.json` | 정상 장애 분석 사례. 실제 `llama3.2:1b` 호출, 참조 로그 ID 2/2 존재, 형식 검사 통과(종료 코드 0). README §4-3 "샘플 1"과 동일한 실행. |
| `result_incident_2_tricky.json` | `result_INC-2026-0002_20260925_121403.json` | 자동 검증(로그 ID 존재 확인)은 통과했지만 AI 답변 내용(의심 원인, 다음 확인 방법)이 부실했던 사례. README §4-3 "샘플 2"와 동일한 실행. |
| `result_adapter_before.json` | `result_INC-2026-0007_20260925_163256_fc04d6e6.json` | CCTV 네트워크 어댑터 장애, **조치 전** 상태 분석. 응답 일부가 한국어/독일어/힌디어가 섞여 깨진 실제 사례. `docs/eval_result_adapter_case.md`에서 평가한 것과 동일한 실행. |
| `result_adapter_after.json` | `result_INC-2026-0008_20260925_163306_2584a164.json` | 같은 CCTV 장비, 어댑터 **교체(조치) 후** 상태 분석. `docs/eval_result_adapter_case.md`에서 평가한 것과 동일한 실행. |

## 읽는 법

각 파일은 `incident_copilot/cli.py`가 실제로 저장한 결과 파일 그대로다. 주요 필드:

- `model_used`, `response_source`: 실제 어떤 모델/호출로 나온 응답인지 (`ollama (실제 LLM 호출)`)
- `processing_status`: 응답 수신 여부, JSON 파싱 여부, 형식(스키마) 통과 여부
- `raw_llm_response`: 모델이 낸 원본 텍스트 (가공 없음)
- `parsed_analysis`: 원본에서 파싱한 의심 원인 / 참조 로그 ID / 다음 확인 방법 / 아직 모르는 것
- `id_existence_check`: 참조한 로그 ID가 입력 로그에 실제로 존재하는지 자동 검사한 결과
- `validation_warnings`: 이 프로그램이 자동으로 낸 내용 경고(과확신 표현, 빈 필드 등)

**주의(스키마 차이)**: `result_incident_2_tricky.json`은 `response_source`/`processing_status`
필드가 도입되기 **전에** 생성된 파일이라 이 두 필드가 없고 대신 `success: true`만 있다. `--offline-response`
기능도 이 파일이 생성된 시점에는 아직 없었으므로, 이 파일은 명명 규칙과 시점상 실제 Ollama 호출임이
분명하지만 최신 파일들처럼 `response_source`로 기계가 바로 구분할 수 있는 필드는 없다 — 오래된
실행 증거를 있는 그대로 남겨 둔 것이며, 내용을 새 스키마에 맞춰 다시 쓰지 않았다.

**주의**: `id_existence_check`가 전부 통과했다고 해서 `parsed_analysis`의 내용이 맞다는 뜻은
아니다 — 그건 사람이 직접 읽고 판단해야 한다(위 표의 `result_incident_2_tricky.json`이 정확히 그
사례다). 자세한 설명은 프로젝트 루트 `README.md`와 `docs/eval_result_adapter_case.md` 참고.
