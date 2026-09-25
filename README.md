# AI Incident Copilot

SK하이닉스 AI 해커톤 2026 제출용 개인 포트폴리오. 입문자가 처음부터 새로 만든 작은 프로젝트이며, 기존에 있던 다른 대형 프로젝트(FastAPI/Docker/K8s)와는 완전히 별개다.

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

이 프로젝트는 그 과정 중 초기 원인 추정과 근거 정리 단계를 LLM이 보조하도록 만든 것이며, 최종 원인 판단과 현장 조치는 여전히 사람이 한다는 원칙을 코드로도 강제한다(§6 참고).

## 3. 실행 방법 (이 PC에서 실제로 확인한 순서)

이 프로젝트는 로컬 PC(원격/클라우드 작업 공간 아님)에서 실행했다. 확인한 근거: 컴퓨터 이름 `DESKTOP-0DO0IA6`, 도메인 미가입(개인 PC), 메인보드 모델 `MS-7D48`(가상머신이 아닌 실제 데스크톱 부품), OS `Windows 11 Home`.

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

이 중 `test_key_with_stray_whitespace_is_normalized`와 `test_bracketed_log_id_is_normalized_and_not_treated_as_hallucination`은 실제로 실행 중 발견한 버그(아래 4-4)를 재현하는 테스트다.

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

**샘플 2 (notification-worker, 정보가 부족한 가상 장애 — 근거 없는 주장 유도용)** — 명령: `python run.py data\sample_incident_2_tricky.json`

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

이 샘플 2 결과가 이 프로젝트의 핵심 포인트를 실제로 보여준다: **참조한 로그 ID 2개는 모두 실제로 존재한다("존재 확인" 통과). 하지만 "의심 원인"은 입력 상태 요약을 그대로 복사한 문장이고, "다음 확인 방법"과 "아직 모르는 것"도 의미 없는 문장을 반복한다.** 즉 ID 존재 확인을 통과했다고 해서 그 내용이 실제로 근거 있는 판단이라는 뜻이 아니다. 이건 미리 짜서 보여준 예시가 아니라, 정보가 부족한 입력을 줬을 때 작은 모델(1B)이 실제로 낸 응답이다.

### 4-4. 실행 중 실제로 발견하고 고친 버그

1. `llama3.2:1b` 모델이 JSON 키 앞에 공백을 붙여서 `" suspected_cause"`처럼 출력한 적이 있었다(원본 응답은 `outputs/result_INC-2026-0001_20260925_120252.json`에 남아 있음). 그 결과 파서가 이 키를 못 찾아서 "의심 원인"이 빈 문자열로 나왔다. `incident_copilot/validator.py`에서 키를 `strip()`으로 정규화해서 고쳤다. 재현 테스트: `test_key_with_stray_whitespace_is_normalized`.
2. 같은 모델이 `referenced_log_ids`를 `["[LOG-101]", "[LOG-102]"]`처럼 대괄호를 붙여서 낸 적이 있었다(프롬프트에서 로그를 `- [LOG-101] ...` 형태로 보여줬기 때문에 그대로 따라 적은 것으로 보임). 이때 검증 로직이 `[LOG-101]`과 `LOG-101`을 다른 문자열로 보고 "존재하지 않는 로그 ID(환각 의심)"라고 잘못 경고했다(원본 응답은 `outputs/result_INC-2026-0002_20260925_121302.json`에 남아 있음). `_normalize_log_id()`를 추가해서 대괄호·공백을 제거한 뒤 비교하도록 고쳤다. 재현 테스트: `test_bracketed_log_id_is_normalized_and_not_treated_as_hallucination`.

## 5. 실패했거나 아직 안 되는 부분 (미완료)

- **미완료**: 근거 없는 주장 감지는 규칙 기반(rule-based)이다 — (a) 참조 로그 ID가 하나도 없는지, (b) "확실히/틀림없이/100%" 같은 과확신 표현이 있는지, (c) "아직 모르는 것"을 하나라도 냈는지만 검사한다. 문장의 논리적 타당성까지 판단하지는 못한다.
- **미완료**: 작은 모델(1B)의 출력 품질이 낮을 때가 있다 (4-3 샘플 2 참고: 의미 없는 "다시 확인" 같은 문장). 더 큰 모델(예: 7B 이상)을 쓰면 나아질 가능성이 있으나 이번 제출에서는 확인하지 않았다.
- **미완료**: JSON 파싱 정규화는 이번에 발견한 "키 공백"과 "로그 ID에 대괄호 포함" 두 패턴만 고쳤다. 다른 형태로 JSON이 깨지는 경우까지 전부 방어하지는 못한다.
- **의도적으로 만들지 않음** (범위 제외, 실패 아님): 웹 화면, Kubernetes, GPU 서버, 데이터베이스.

## 6. AI에게 맡긴 일 vs 사람이 판단해야 하는 일

| 영역 | 담당 |
|---|---|
| 로그를 보고 1차 원인 후보를 빠르게 추려보는 것 | AI |
| 어떤 로그를 근거로 그 후보를 골랐는지 텍스트로 밝히는 것 | AI |
| 인용한 로그 ID가 입력에 실제로 존재하는지 기계적으로 확인 | 프로그램(자동 검증) |
| 그 로그가 실제로 원인을 입증하는지, 원인이 실제로 맞는지 최종 판단 | **사람** |
| 다음에 무엇을 확인해볼지 아이디어 제시 | AI (참고용) |
| 실제 조치(재배포, 설정 변경, 현장 출동 등) 결정 및 실행 | **사람** |

## 7. 가상 데이터 안내

`data/` 폴더의 모든 로그는 이 포트폴리오를 위해 만든 **가상 데이터**다. 실제 회사, 실제 서비스, 실제 장애와 무관하다.
