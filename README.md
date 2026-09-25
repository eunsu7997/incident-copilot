# AI Incident Copilot

운영 장애 로그를 바탕으로 LLM이 원인 후보와 확인 항목을 제안하고, 인용한 로그 ID의 존재 여부를 자동 검증하는 Python 명령줄 도구입니다. ITS 장비 유지보수 경험에서 출발했습니다.

SK하이닉스 AI 해커톤 2026 제출용 개인 포트폴리오이며, 기존에 있던 다른 대형 프로젝트(FastAPI/Docker/K8s)와는 완전히 별개다.

## 1. 문제 정의

운영 중인 시스템에 장애가 나면 담당자는 짧은 시간 안에 로그와 상태 정보만 보고 "무엇이 원인일 것 같은지"를 추정해야 한다. 이때 흔한 문제는 두 가지다.

1. 정보가 부족한데도 담당자(또는 AI)가 원인을 너무 빨리 확정해버리는 것
2. 어떤 로그를 근거로 그렇게 판단했는지가 기록에 남지 않아서, 나중에 다른 사람이 그 판단을 검증할 수 없는 것

이 프로젝트는 LLM(거대 언어모델)에게 장애 로그를 주고 "의심 원인 / 그 판단에 쓴 로그 ID / 다음 확인 방법 / 아직 모르는 것"을 강제로 구조화해서 답하게 하고, **AI가 인용한 로그 ID가 실제로 입력에 있는지**를 프로그램이 자동으로 검사한다. 다만 이 검사는 "그 로그 ID가 실제로 존재하는가"만 확인하는 것이며, "그 로그가 정말로 원인을 입증하는가"는 검사하지 않는다 — 그 부분은 사람이 로그 내용을 직접 읽고 판단해야 한다. 이 구분을 프로그램 출력과 결과 파일에 명시적으로 분리해서 보여준다.

## 2. 내 ITS 현장 경험과의 연결

ITS는 여기서 "IT 서비스"가 아니라 **지능형교통체계(Intelligent Transport Systems)**를 의미한다. 나는 ITS 현장에서 CCTV/VMS 등 장비의 유지보수 경험이 있다. 현장에서 장비 장애가 발생했을 때 실제로 겪는 상황은 이 프로젝트의 문제 정의와 거의 같다.

- 현장 로그·상태 정보는 항상 불완전하다 (카메라 통신 끊김, VMS 표출 오류 등 원인 후보가 여러 개 겹쳐 보일 때가 많음).
- 담당자는 제한된 정보로 "가장 의심되는 원인"을 먼저 추정하고, 현장에 나가기 전에 "무엇을 더 확인해야 하는지"를 정리한다.
- 이때 근거 없이 원인을 확정하면 잘못된 조치(예: 불필요한 장비 교체, 헛걸음)로 이어질 수 있다. 그래서 "이 로그 때문에 이렇게 의심한다"는 근거를 남기고, "아직 모르는 것"을 분리해서 인지하는 습관이 실제로 중요하다.

이 프로젝트는 그 과정 중 초기 원인 추정과 근거 정리 단계를 LLM이 보조하도록 만든 것이며, 최종 원인 판단과 현장 조치는 여전히 사람이 해야 한다는 점을 프로그램 출력에 명시적으로 표시한다(§6 참고). 다만 이건 화면/결과 파일에 문구로 안내하는 것일 뿐, 사람이 실제로 검토했는지를 프로그램이 기술적으로 강제하지는 않는다.

## 3. 실행 방법 (이 PC에서 실제로 확인한 순서)

이 프로젝트는 원격/클라우드 작업 공간이 아닌 로컬 PC에서 실행했다(도메인에 가입되지 않은 개인 PC로 확인함). 재현에 필요한 환경 정보만 남긴다.

- OS: Windows 11 Home
- Python: 3.14.7
- Ollama: 0.34.4, 모델 `llama3.2:1b`

```powershell
# 1) 가상환경(venv, virtual environment = 프로젝트 전용 파이썬 환경) 생성
python -m venv .venv

# 2) 가상환경 안의 파이썬으로 패키지 설치
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# 3) (터미널에서 직접 활성화하고 싶다면 — 선택사항)
.\.venv\Scripts\Activate.ps1

# 4) Ollama(로컬에서 LLM을 실행해주는 프로그램)로 작은 모델 받기
ollama pull llama3.2:1b

# 5) 오프라인 검증 로직 테스트 실행 (LLM 호출 없이 규칙 검증만 확인)
.\.venv\Scripts\python.exe -m pytest tests\ -v

# 6) 실제 LLM 호출 (가상 장애 데이터 1건)
.\.venv\Scripts\python.exe run.py data\sample_incident_1.json
.\.venv\Scripts\python.exe run.py data\sample_incident_2_tricky.json

# 7) (데모) 존재하지 않는 로그 ID 경고를 실제 CLI 화면으로 보고 싶다면 — LLM 호출 없이 검증 로직만 실행
.\.venv\Scripts\python.exe run.py data\sample_incident_1.json --offline-response data\demo_manual_response_missing_id.txt
```

`data/sample_incident_1.json`, `data/sample_incident_2_tricky.json`은 모두 **가상(virtual) 데이터**이며 실제 회사/서비스와 무관하다.

## 4. 실제 실행 결과

### 4-1. venv 문제 (오늘 확인한 사실만 기록 — 어제 오류의 정확한 원인은 추측하지 않음)

- 어제 venv 생성이 실패했다고 했으나, 그때의 정확한 오류 메시지를 오늘 다시 확인하거나 재현할 수는 없었다. 따라서 어제 실패의 원인을 추측해서 단정하지 않는다.
- 오늘 이 폴더에서 `python -m venv .venv`는 문제 없이 성공했다(exit code 0).
- 다만 확인 과정에서 이 사용자 계정의 PowerShell 실행 정책(Execution Policy)이 `RemoteSigned`/`Bypass`가 아닌 상태였던 것을 발견했다. Windows PowerShell은 기본적으로 `.ps1` 스크립트 실행을 제한하는 경우가 있고, venv의 `Activate.ps1`도 `.ps1` 스크립트이기 때문에, 이 설정이 원인이면 "생성은 되지만 활성화(activate)만 안 되는" 증상으로 나타날 수 있다. 재발 방지를 위해 현재 사용자 범위로 아래처럼 변경해 두었다:
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```
- 결론: **오늘 venv 생성·활성화는 정상 동작을 확인**했다. 어제 실패의 정확한 원인은 "모름"으로 남긴다.

### 4-2. 오프라인 검증 로직 테스트 (pytest, LLM 미호출)

```
tests/test_validator.py::test_normal_case_no_warnings PASSED
tests/test_validator.py::test_hallucinated_log_id_triggers_warning PASSED
tests/test_validator.py::test_ungrounded_overconfident_claim_triggers_multiple_warnings PASSED
tests/test_validator.py::test_key_with_stray_whitespace_is_normalized PASSED
tests/test_validator.py::test_bracketed_log_id_is_normalized_and_not_treated_as_hallucination PASSED
tests/test_validator.py::test_non_json_response_marked_as_parse_failure PASSED
6 passed in 0.02s
```

이 중 `test_key_with_stray_whitespace_is_normalized`와 `test_bracketed_log_id_is_normalized_and_not_treated_as_hallucination`은 실제로 실행 중 발견한 버그(아래 4-5)를 재현하는 테스트다.

### 4-3. 실제 LLM 호출 결과 (model: `llama3.2:1b`, Ollama 로컬 실행)

**샘플 1 (order-api, 근거가 비교적 명확한 가상 장애)** — 명령: `python run.py data\sample_incident_1.json`

```
[의심 원인]
DB connection pool 사용량 97% 대기 중인 커넥션 요청 다수 발생

[참조한 로그 ID]
['LOG-005', 'LOG-006']

[참조 ID 존재 확인] 2/2개가 실제 입력 로그에 존재함
  -> 주의: 이건 'ID가 입력 로그 목록에 있는가'만 자동으로 확인한 것입니다. 그 로그가 실제로 의심 원인을 뒷받침하는지는 검사하지 않습니다.
[원인 판단] AI의 추정일 뿐이며, 실제로 맞는지는 사람이 로그 내용을 읽고 직접 검토해야 합니다.
```
전체 결과: `outputs/result_INC-2026-0001_20260925_121228.json`

![정상 실행 결과](screenshots/normal_case.png)
위 스크린샷은 `run.py`로 샘플 1(order-api)을 정상 실행했을 때의 실제 화면이다.

**샘플 2 (notification-worker, 정보가 부족한 가상 장애 — 자동 검증의 한계를 보여준 실제 모델 응답)** — 명령: `python run.py data\sample_incident_2_tricky.json`

```
[의심 원인]
알림 발송이 일부 누락되었다는 사용자 문의가 접수됨

[참조한 로그 ID]
['LOG-101', 'LOG-102']

[다음 확인 방법]
  1. 일시적 확인
  2. 다시 확인

[아직 모르는 것]
  1. 알림 발송이 일부 누락되었다는 사용자 문의가 접수됨

[참조 ID 존재 확인] 2/2개가 실제 입력 로그에 존재함
```
전체 결과: `outputs/result_INC-2026-0002_20260925_121403.json`

이 샘플 2 결과는 **자동 검증(로그 ID 존재 확인)이 통과해도 AI 답변 내용 자체가 부실할 수 있다는 것**을 실제 모델 응답으로 보여준다. 정확히 말하면: 참조한 로그 ID 2개는 모두 실제로 존재해서 "참조 ID 존재 확인"은 통과했다. 하지만 "의심 원인"은 입력 상태 요약을 그대로 복사한 문장이고, "다음 확인 방법"과 "아직 모르는 것"도 의미 없는 문장을 반복한다. 즉 이 프로그램의 자동 검증은 "인용한 ID가 실제로 존재하는가"만 확인할 뿐, "AI가 낸 내용이 실제로 쓸모 있는 판단인가"는 검사하지 못한다는 한계를 그대로 드러낸다. 이건 미리 짜서 보여준 예시가 아니라, 정보가 부족한 입력을 줬을 때 작은 모델(1B)이 실제로 낸 응답이다.

### 4-4. 존재하지 않는 로그 ID를 인용하면 실제로 경고가 뜨는 장면 (실제 CLI 실행)

위 §4-2의 pytest 테스트는 이 경고 로직이 코드상으로 맞다는 것만 보여준다. 실제 CLI 화면에서도 같은 동작을 보여주기 위해, 사람이 직접 작성한 예시 응답 파일(`data/demo_manual_response_missing_id.txt`, 실제 LLM 호출이 아님을 명시)에 실제로 존재하지 않는 로그 ID `LOG-999`를 하나 끼워 넣고, `--offline-response` 옵션으로 실제 CLI(`run.py`)의 검증 로직을 통과시켰다.

입력한 예시 응답(`data/demo_manual_response_missing_id.txt`, 사람이 직접 작성 — 실제 LLM 응답 아님):
```json
{
  "suspected_cause": "DB 커넥션 풀 부족으로 인한 타임아웃으로 추정됩니다.",
  "referenced_log_ids": ["LOG-003", "LOG-999"],
  "next_steps": ["DB 커넥션 풀 설정 변경 이력을 확인한다"],
  "unknowns": ["LOG-999가 정확히 어떤 로그인지 확인이 필요하다"]
}
```
(`sample_incident_1.json`에는 `LOG-001`~`LOG-007`만 있고 `LOG-999`는 없다.)

실행 명령과 실제 화면:
```
> python run.py data\sample_incident_1.json --offline-response data\demo_manual_response_missing_id.txt

[알림] --offline-response 옵션 사용 중: 실제 LLM을 호출하지 않습니다.
아래 결과는 'data\demo_manual_response_missing_id.txt'에 사람이 미리 작성해 둔 예시 응답을 검증 로직에 통과시킨 것이며, 실제 LLM 실행 결과가 아닙니다 (검증 로직 데모용).

[참조한 로그 ID]
['LOG-003', 'LOG-999']

--- 검증 결과 (이 프로그램이 자동으로 확인한 것) ---
[참조 ID 존재 확인] 1/2개가 실제 입력 로그에 존재함, 존재하지 않는 ID: ['LOG-999']
  -> 주의: 이건 'ID가 입력 로그 목록에 있는가'만 자동으로 확인한 것입니다. 그 로그가 실제로 의심 원인을 뒷받침하는지는 검사하지 않습니다.
[원인 판단] AI의 추정일 뿐이며, 실제로 맞는지는 사람이 로그 내용을 읽고 직접 검토해야 합니다.

--- 추가 검증 경고 ---
  ⚠ 존재하지 않는 로그 ID를 인용했습니다 (환각 의심): ['LOG-999']
```
전체 결과: `outputs/result_INC-2026-0001_20260925_122618.json`

![존재하지 않는 로그 ID 경고](screenshots/hallucination_warning.png)
위 스크린샷은 존재하지 않는 로그 ID(`LOG-999`)를 인용하면 경고가 뜨는 화면이다. `--offline-response` 옵션으로 사람이 미리 작성한 예시 응답을 검증 로직에 통과시킨 것이며, 실제 LLM 실행 결과가 아니다.

### 4-5. 실행 중 실제로 발견하고 고친 버그

1. `llama3.2:1b` 모델이 JSON 키 앞에 공백을 붙여서 `" suspected_cause"`처럼 출력한 적이 있었다(원본 응답은 `outputs/result_INC-2026-0001_20260925_120252.json`에 남아 있음). 그 결과 파서가 이 키를 못 찾아서 "의심 원인"이 빈 문자열로 나왔다. `incident_copilot/validator.py`에서 키를 `strip()`으로 정규화해서 고쳤다. 재현 테스트: `test_key_with_stray_whitespace_is_normalized`.
2. 같은 모델이 `referenced_log_ids`를 `["[LOG-101]", "[LOG-102]"]`처럼 대괄호를 붙여서 낸 적이 있었다(프롬프트에서 로그를 `- [LOG-101] ...` 형태로 보여줬기 때문에 그대로 따라 적은 것으로 보임). 이때 검증 로직이 `[LOG-101]`과 `LOG-101`을 다른 문자열로 보고 "존재하지 않는 로그 ID(환각 의심)"라고 잘못 경고했다(원본 응답은 `outputs/result_INC-2026-0002_20260925_121302.json`에 남아 있음). `_normalize_log_id()`를 추가해서 대괄호·공백을 제거한 뒤 비교하도록 고쳤다. 재현 테스트: `test_bracketed_log_id_is_normalized_and_not_treated_as_hallucination`.

## 5. 실패했거나 아직 안 되는 부분 (미완료)

- **미완료**: 근거 없는 주장 감지는 규칙 기반(rule-based)이다 — (a) 참조 로그 ID가 하나도 없는지, (b) "확실히/틀림없이/100%" 같은 과확신 표현이 있는지, (c) "아직 모르는 것"을 하나라도 냈는지만 검사한다. 문장의 논리적 타당성까지 판단하지는 못한다.
- **미완료**: 작은 모델(1B)의 출력 품질이 낮을 때가 있다 (4-3 샘플 2, §8 참고: 의미 없는 문장 반복, 간헐적으로 한국어 대신 영어로 답변).
- **미완료**: JSON 파싱 정규화는 이번에 발견한 "키 공백"과 "로그 ID에 대괄호 포함" 두 패턴만 고쳤다. 다른 형태로 JSON이 깨지는 경우까지 전부 방어하지는 못한다.
- **미완료**: Ollama 응답이 120초를 넘으면 타임아웃 처리하도록 되어 있는데(§8 참고), 실제로 한 번 이 타임아웃이 발생했다. 관찰한 1건은 재시도 후 응답을 받았다. 타임아웃 값을 늘리거나 재시도 로직을 자동화하지는 않았다.
- **의도적으로 만들지 않음** (범위 제외, 실패 아님): 웹 화면, Kubernetes, GPU 서버, 데이터베이스.

## 6. AI에게 맡긴 일 vs 사람이 판단해야 하는 일

### 6-1. 프로그램 "사용 중"의 역할 분담

| 영역 | 담당 |
|---|---|
| 로그를 보고 1차 원인 후보를 빠르게 추려보는 것 | AI |
| 어떤 로그를 근거로 그 후보를 골랐는지 텍스트로 밝히는 것 | AI |
| 인용한 로그 ID가 입력에 실제로 존재하는지 기계적으로 확인 | 프로그램(자동 검증) |
| 그 로그가 실제로 원인을 입증하는지, 원인이 실제로 맞는지 최종 판단 | **사람** |
| 다음에 무엇을 확인해볼지 아이디어 제시 | AI (참고용) |
| 실제 조치(재배포, 설정 변경, 현장 출동 등) 결정 및 실행 | **사람** |

### 6-2. 개발 과정에서의 역할 분담

이 프로젝트는 Claude Code(AI 코딩 도구)를 사용해서 만들었다. 실제로 있었던 역할 분담은 다음과 같다.

| 영역 | 담당 |
|---|---|
| 무엇을 만들지(요구사항), 출력 형식, 범위(웹/K8s/DB 제외 등) 결정 | **사람(나)** |
| README 표현이 과장됐는지, 사실과 다른지 확인하고 수정 지시 | **사람(나)** |
| 실제 실행 결과(터미널 화면, 결과 파일, 스크린샷)가 요구사항대로 나왔는지 확인 | **사람(나)** |
| 커밋 시점과 커밋 메시지 승인, git 작성자 정보 결정 | **사람(나)** |
| Python 코드 작성(`incident_copilot/` 모듈, `run.py`, 테스트) | Claude Code |
| 터미널 명령 실행(venv 생성, 패키지 설치, Ollama 설치·모델 다운로드, `pytest`/`run.py` 실행) | Claude Code |
| 실행 중 발견된 버그(예: JSON 키 공백, 로그 ID 대괄호) 원인 파악 및 수정 | Claude Code |
| README 초안 작성 및 사람의 수정 지시 반영 | Claude Code |

즉 무엇을 만들 것인지·결과가 맞는지에 대한 판단은 사람이 했고, 코드 작성과 명령 실행은 Claude Code가 했다. "내가 코딩했다"고 과장하지 않기 위해 이 구분을 그대로 남긴다.

## 7. 가상 데이터 안내

`data/` 폴더의 모든 로그는 이 포트폴리오를 위해 만든 **가상 데이터**다. 실제 회사, 실제 서비스, 실제 장애와 무관하다.

## 8. 추가 장애 유형 테스트

기존 2개 샘플(§4) 외에, 서로 다른 장애 유형 4종을 추가로 만들어서 각각 `run.py`로 실제 실행했다. 모두 `llama3.2:1b` 모델, Ollama 로컬 실행 기준이다.

"실행 결과" 열의 "응답 수신·검증 처리 완료"는 프로그램이 LLM 응답을 받아 검증 절차(파싱, 로그 ID 존재 확인)를 끝까지 처리했다는 뜻일 뿐, 원인 분석 내용이 정확했다는 뜻이 아니다. 내용 품질은 "비고" 열과 §4-3, §5를 참고할 것.

| 샘플 파일 | 장애 유형 | 실행 결과 | 참조 로그ID 검증 | 비고 |
|---|---|---|---|---|
| `data/sample_incident_3_network_latency.json` | 네트워크 지연 (API 게이트웨이) | 응답 수신·검증 처리 완료 | 7/7 존재 | - |
| `data/sample_incident_4_disk_storage.json` | 디스크/스토리지 포화 | **1차 실패 → 재시도 후 응답 수신·검증 처리 완료** | 5/5 존재 | 1차 시도에서 `Ollama 응답이 120초 안에 오지 않았습니다(timeout)` 오류로 실패함(원본 오류는 아래 참고). 재시도하니 응답을 받았다. 원인은 확인하지 못했다(모델 재로딩으로 추정하지만 확인된 사실은 아니다). |
| `data/sample_incident_5_auth_error.json` | 인증(로그인) 오류 | 응답 수신·검증 처리 완료 | 5/5 존재 | 의심 원인이 한국어가 아니라 영어("Token validation timeout")로 나옴 — 시스템 프롬프트는 한국어로 답하라고 지시했지만 작은 모델이 이를 항상 지키지는 않았다. |
| `data/sample_incident_6_fab_equipment.json` | 가상 반도체 FAB 설비 온도 이상 (SK하이닉스 해커톤 맥락, 완전 가상 시나리오) | 응답 수신·검증 처리 완료 | 3/3 존재 | "다음 확인 방법"과 "아직 모르는 것"에 같은 문장이 반복됨(품질 낮음) |

4건 모두 프로그램이 최종적으로 응답을 받아 검증 절차를 끝까지 처리했고, 4건 모두에서 AI가 인용한 로그 ID는 전부 실제 입력 로그에 존재했다(환각 경고 없음). 다만 이건 프로그램이 정상 동작했다는 뜻이며, AI가 낸 원인 분석 내용까지 정확했다는 뜻은 아니다 — 위 표처럼 (1) 일시적 타임아웃, (2) 언어 미준수(영어 혼용), (3) 반복적/의미 없는 문장 같은 품질 문제는 실제로 관찰됐다 — 이 역시 "미완료"(§5)에 반영했다. 전체 실행 결과 파일: `outputs/result_INC-2026-0003_*.json` ~ `outputs/result_INC-2026-0006_*.json`.

원본 타임아웃 오류(1차 시도, 재시도로 해결됨):
```
[실패] LLM 호출 중 오류가 발생했습니다:
Ollama 응답이 120초 안에 오지 않았습니다(timeout). 원본 오류: HTTPConnectionPool(host='localhost', port=11434): Read timed out. (read timeout=120)
```
