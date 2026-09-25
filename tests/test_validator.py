"""validator.py에 대한 테스트.

여기서는 실제 LLM을 호출하지 않는다(오프라인 테스트). 대신 'LLM이 이런 텍스트를 냈다고 가정하면
검증 로직이 올바르게 동작하는가'를 검사한다.

케이스 1: 정상적으로 작동하는 사례 (근거 있는 답변, 경고 없어야 함)
케이스 2: 존재하지 않는 로그 ID를 인용한 사례 (경고 발생해야 함)
케이스 3: 근거(참조 로그) 없이 확신하는 표현을 쓴 사례 (경고 여러 개 발생해야 함)
케이스 4: JSON이 아닌 응답 (파싱 실패로 처리되어야 함)
"""
from incident_copilot.validator import parse_ai_response, validate

VALID_IDS = {"LOG-001", "LOG-002", "LOG-003", "LOG-004"}


def test_normal_case_no_warnings():
    raw = """{
        "suspected_cause": "DB 커넥션 풀 축소 설정 변경 이후 커넥션 부족으로 타임아웃이 발생했을 가능성이 있습니다.",
        "referenced_log_ids": ["LOG-002", "LOG-003"],
        "next_steps": ["DB 커넥션 풀 최대 크기 설정 이력을 확인한다", "타임아웃 발생 시점의 동시 요청 수를 확인한다"],
        "unknowns": ["실제 동시 접속자 수 데이터는 로그에 없어 확인이 필요하다"]
    }"""
    analysis = parse_ai_response(raw)
    result = validate(analysis, VALID_IDS)
    assert result.parse_ok is True
    assert result.warnings == []


def test_hallucinated_log_id_triggers_warning():
    raw = """{
        "suspected_cause": "네트워크 장비 문제로 추정됩니다.",
        "referenced_log_ids": ["LOG-999"],
        "next_steps": ["네트워크 장비 로그를 확인한다"],
        "unknowns": ["정확한 장비명은 알 수 없다"]
    }"""
    analysis = parse_ai_response(raw)
    result = validate(analysis, VALID_IDS)
    assert result.parse_ok is True
    assert any("존재하지 않는 로그 ID" in w for w in result.warnings)


def test_ungrounded_overconfident_claim_triggers_multiple_warnings():
    raw = """{
        "suspected_cause": "이것은 100% 확실히 메모리 누수 때문입니다. 틀림없이 그렇습니다.",
        "referenced_log_ids": [],
        "next_steps": ["재배포한다"],
        "unknowns": []
    }"""
    analysis = parse_ai_response(raw)
    result = validate(analysis, VALID_IDS)
    assert result.parse_ok is True
    warning_text = " ".join(result.warnings)
    assert "참조한 로그 ID가 하나도 없습니다" in warning_text
    assert "과도하게 확신하는 표현" in warning_text
    assert "아직 모르는 것" in warning_text
    assert len(result.warnings) >= 3


def test_key_with_stray_whitespace_is_normalized():
    """llama3.2:1b가 실제로 낸 것처럼 키 앞에 공백이 붙은 경우 (예: " suspected_cause")도
    정상적으로 인식되어야 한다. 이 테스트는 실제 실행 중 발견된 버그를 재현한다."""
    raw = '{ " suspected_cause": "DB 커넥션 풀 문제로 추정", "referenced_log_ids": ["LOG-002"], "next_steps": [], "unknowns": [] }'
    analysis = parse_ai_response(raw)
    assert analysis.suspected_cause == "DB 커넥션 풀 문제로 추정"


def test_bracketed_log_id_is_normalized_and_not_treated_as_hallucination():
    """llama3.2:1b가 실제로 낸 것처럼 로그 ID에 대괄호를 붙여 '[LOG-002]'처럼 내보내도,
    실제로 존재하는 LOG-002를 인용한 것으로 인식되어야 한다(잘못된 환각 경고 방지).
    이 테스트는 sample_incident_2_tricky.json 실행 중 실제로 발견된 버그를 재현한다."""
    raw = """{
        "suspected_cause": "DB 지연으로 추정",
        "referenced_log_ids": ["[LOG-002]", " [LOG-003] "],
        "next_steps": ["DB 지표를 확인한다"],
        "unknowns": ["정확한 동시 요청 수는 알 수 없다"]
    }"""
    analysis = parse_ai_response(raw)
    assert analysis.referenced_log_ids == ["LOG-002", "LOG-003"]
    result = validate(analysis, VALID_IDS)
    assert result.missing_ids == []
    assert result.existing_ids == ["LOG-002", "LOG-003"]


def test_non_json_response_marked_as_parse_failure():
    raw = "죄송하지만 형식을 지키지 않고 그냥 문장으로 답변합니다."
    analysis = parse_ai_response(raw)
    result = validate(analysis, VALID_IDS)
    assert result.parse_ok is False
    assert any("JSON" in w for w in result.warnings)
