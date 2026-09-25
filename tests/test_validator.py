"""validator.py에 대한 테스트.

여기서는 실제 LLM을 호출하지 않는다(오프라인 테스트). 대신 'LLM이 이런 텍스트를 냈다고 가정하면
파싱/형식 검사/내용 검증 로직이 올바르게 동작하는가'를 검사한다.

이 파일의 뒷부분(test_top_level_*, test_referenced_log_ids_as_*, test_missing_*,
test_wrong_type_*)은 코드 리뷰에서 실제로 재현된 버그를 재현하는 회귀 테스트다:
- 응답이 "[]" 또는 "null"이면 예전 코드는 AttributeError로 죽었다.
- referenced_log_ids가 숫자면 예전 코드는 TypeError로 죽었다.
- referenced_log_ids가 "LOG-001" 같은 문자열이면 예전 코드는 글자 하나씩 쪼개서 조용히 틀린
  결과를 만들었다(크래시는 안 나지만 결과가 틀림).
지금은 이 세 경우 모두 예외를 던지지 않고, schema_valid=False와 구체적인 format_errors로 보고한다.
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
    parsed = parse_ai_response(raw)
    assert parsed.schema_valid is True
    result = validate(parsed, VALID_IDS)
    assert result.format_valid is True
    assert result.warnings == []


def test_hallucinated_log_id_triggers_warning():
    raw = """{
        "suspected_cause": "네트워크 장비 문제로 추정됩니다.",
        "referenced_log_ids": ["LOG-999"],
        "next_steps": ["네트워크 장비 로그를 확인한다"],
        "unknowns": ["정확한 장비명은 알 수 없다"]
    }"""
    parsed = parse_ai_response(raw)
    result = validate(parsed, VALID_IDS)
    assert result.format_valid is True
    assert any("존재하지 않는 로그 ID" in w for w in result.warnings)


def test_ungrounded_overconfident_claim_triggers_multiple_warnings():
    raw = """{
        "suspected_cause": "이것은 100% 확실히 메모리 누수 때문입니다. 틀림없이 그렇습니다.",
        "referenced_log_ids": [],
        "next_steps": ["재배포한다"],
        "unknowns": []
    }"""
    parsed = parse_ai_response(raw)
    result = validate(parsed, VALID_IDS)
    assert result.format_valid is True
    warning_text = " ".join(result.warnings)
    assert "참조한 로그 ID가 하나도 없습니다" in warning_text
    assert "과도하게 확신하는 표현" in warning_text
    assert "아직 모르는 것" in warning_text
    assert len(result.warnings) >= 3


def test_key_with_stray_whitespace_is_normalized():
    """llama3.2:1b가 실제로 낸 것처럼 키 앞에 공백이 붙은 경우 (예: " suspected_cause")도
    정상적으로 인식되어야 한다. 이 테스트는 실제 실행 중 발견된 버그를 재현한다."""
    raw = '{ " suspected_cause": "DB 커넥션 풀 문제로 추정", "referenced_log_ids": ["LOG-002"], "next_steps": ["확인한다"], "unknowns": ["모른다"] }'
    parsed = parse_ai_response(raw)
    assert parsed.schema_valid is True
    assert parsed.analysis.suspected_cause == "DB 커넥션 풀 문제로 추정"


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
    parsed = parse_ai_response(raw)
    assert parsed.analysis.referenced_log_ids == ["LOG-002", "LOG-003"]
    result = validate(parsed, VALID_IDS)
    assert result.missing_ids == []
    assert result.existing_ids == ["LOG-002", "LOG-003"]


def test_non_json_response_is_reported_as_format_error():
    raw = "죄송하지만 형식을 지키지 않고 그냥 문장으로 답변합니다."
    parsed = parse_ai_response(raw)
    assert parsed.json_parsed is False
    assert parsed.schema_valid is False
    assert parsed.analysis is None
    result = validate(parsed, VALID_IDS)
    assert result.format_valid is False
    assert any("JSON" in w for w in result.warnings)


# --- 아래부터는 코드 리뷰에서 실제로 재현된 버그에 대한 회귀 테스트 ---


def test_top_level_null_response_does_not_crash():
    """AI 응답이 'null' 하나뿐이면 예전 코드는 None.get()에서 AttributeError로 죽었다.
    지금은 크래시 없이 schema_valid=False와 구체적인 오류 메시지로 보고해야 한다."""
    raw = "null"
    parsed = parse_ai_response(raw)  # 예외가 나면 이 줄에서 테스트가 바로 실패한다
    assert parsed.json_parsed is True
    assert parsed.schema_valid is False
    assert parsed.analysis is None
    assert any("NoneType" in e for e in parsed.format_errors)
    assert parsed.raw_response == "null"


def test_top_level_list_response_does_not_crash():
    """AI 응답이 '[]'(빈 배열)이면 예전 코드는 list.get()에서 AttributeError로 죽었다."""
    raw = "[]"
    parsed = parse_ai_response(raw)
    assert parsed.json_parsed is True
    assert parsed.schema_valid is False
    assert parsed.analysis is None
    assert any("list" in e for e in parsed.format_errors)


def test_referenced_log_ids_as_number_does_not_crash():
    """referenced_log_ids가 숫자면 예전 코드는 list(5)에서 TypeError로 죽었다."""
    raw = """{
        "suspected_cause": "추정 원인",
        "referenced_log_ids": 5,
        "next_steps": ["확인한다"],
        "unknowns": ["모른다"]
    }"""
    parsed = parse_ai_response(raw)  # 예외가 나면 이 줄에서 테스트가 바로 실패한다
    assert parsed.schema_valid is False
    assert parsed.analysis is None
    assert any("referenced_log_ids" in e and "int" in e for e in parsed.format_errors)


def test_referenced_log_ids_as_string_is_rejected_not_split_into_chars():
    """referenced_log_ids가 "LOG-001"처럼 문자열이면 예전 코드는 list("LOG-001")로
    글자를 하나씩 쪼개서('L','O','G',...) 조용히 틀린 결과를 냈다. 지금은 이를 형식 오류로
    거부해야 하며, 절대로 문자 단위로 쪼개서 analysis를 만들면 안 된다."""
    raw = """{
        "suspected_cause": "추정 원인",
        "referenced_log_ids": "LOG-001",
        "next_steps": ["확인한다"],
        "unknowns": ["모른다"]
    }"""
    parsed = parse_ai_response(raw)
    assert parsed.schema_valid is False
    assert parsed.analysis is None
    assert any("referenced_log_ids" in e and "str" in e for e in parsed.format_errors)


def test_missing_required_key_is_reported():
    raw = """{
        "suspected_cause": "추정 원인",
        "referenced_log_ids": ["LOG-001"],
        "next_steps": ["확인한다"]
    }"""
    parsed = parse_ai_response(raw)
    assert parsed.schema_valid is False
    assert any("'unknowns'" in e for e in parsed.format_errors)


def test_wrong_type_for_suspected_cause_is_reported():
    raw = """{
        "suspected_cause": 123,
        "referenced_log_ids": ["LOG-001"],
        "next_steps": ["확인한다"],
        "unknowns": ["모른다"]
    }"""
    parsed = parse_ai_response(raw)
    assert parsed.schema_valid is False
    assert any("suspected_cause" in e for e in parsed.format_errors)


def test_empty_suspected_cause_triggers_content_warning():
    """형식은 맞지만(문자열은 문자열) 내용이 빈 문자열이면 내용 경고를 내야 한다."""
    raw = """{
        "suspected_cause": "",
        "referenced_log_ids": ["LOG-001"],
        "next_steps": ["확인한다"],
        "unknowns": ["모른다"]
    }"""
    parsed = parse_ai_response(raw)
    assert parsed.schema_valid is True
    result = validate(parsed, VALID_IDS)
    assert any("의심 원인" in w and "비어" in w for w in result.warnings)


def test_empty_next_steps_triggers_content_warning():
    raw = """{
        "suspected_cause": "추정 원인",
        "referenced_log_ids": ["LOG-001"],
        "next_steps": [],
        "unknowns": ["모른다"]
    }"""
    parsed = parse_ai_response(raw)
    assert parsed.schema_valid is True
    result = validate(parsed, VALID_IDS)
    assert any("다음 확인 방법" in w and "비어" in w for w in result.warnings)
