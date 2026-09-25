"""AI 응답 파싱 및 검증.

이 모듈은 세 단계를 분리해서 처리한다 (사람이 반드시 확인해야 하는 부분):
1. JSON 파싱 — AI 응답 텍스트가 JSON으로 해석되는가.
2. 형식(스키마) 검사 — 최상위 객체가 dict인가, 필수 키(suspected_cause/referenced_log_ids/
   next_steps/unknowns)가 다 있는가, 각 필드의 자료형이 맞는가(문자열/배열/배열 원소 문자열).
   이 단계를 통과하지 못하면 절대로 강제 변환하지 않고 명확한 오류로 처리한다 (AIAnalysis를
   만들지 않는다). 원본 응답(raw_response)은 항상 보존한다.
3. 내용 검증 — 존재하지 않는 로그 ID 인용, 근거 없음, 과확신 표현, 빈 필드 등을 경고로 표시한다.
   이 경고들은 "형식은 맞지만 내용이 의심스럽다"는 뜻이며, 형식 오류와는 다르다.
"""
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

from .models import AIAnalysis

OVERCONFIDENT_PHRASES = ["확실히", "틀림없이", "100%", "명백히", "당연히", "확정적으로"]

REQUIRED_KEYS = ("suspected_cause", "referenced_log_ids", "next_steps", "unknowns")
LIST_KEYS = ("referenced_log_ids", "next_steps", "unknowns")


def _normalize_log_id(value) -> str:
    """모델이 로그 ID를 '[LOG-101]'처럼 대괄호를 붙여 내보내는 경우가 있어(프롬프트에
    로그를 "- [LOG-101] ..." 형태로 보여줬기 때문에 그대로 따라 적는 것으로 보임),
    실제 ID 존재 여부를 비교하기 전에 대괄호와 앞뒤 공백을 제거해 정규화한다."""
    return str(value).strip().strip("[]").strip()


def _extract_json(raw_text: str):
    """raw_text에서 JSON을 파싱한다. 성공하면 (data, None), 실패하면 (None, 오류메시지)를 반환한다."""
    text = raw_text.strip()
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None, "AI 응답에서 JSON 객체를 찾을 수 없습니다 (중괄호로 감싼 JSON이 없음)."
    try:
        return json.loads(match.group(0)), None
    except json.JSONDecodeError as e:
        return None, f"JSON 파싱에 실패했습니다: {e}"


def _normalize_keys(data):
    """작은 모델(예: llama3.2:1b)이 가끔 키 앞뒤에 공백을 붙여서 내보내는 경우가 있어
    (예: " suspected_cause") 키를 strip() 해서 정규화한다. dict가 아니면 그대로 반환한다."""
    if isinstance(data, dict):
        return {(k.strip() if isinstance(k, str) else k): v for k, v in data.items()}
    return data


def _validate_schema(data) -> List[str]:
    """data가 기대하는 형식(최상위 dict, 필수 키, 필드 자료형, 배열 원소 자료형)을 만족하는지
    검사해서 문제 목록을 반환한다. 문제가 없으면 빈 리스트를 반환한다.

    여기서 걸러지지 않으면 이후 단계에서 AttributeError/TypeError 없이 안전하게
    AIAnalysis를 만들 수 있다는 것이 이 함수의 목적이다."""
    errors: List[str] = []
    if not isinstance(data, dict):
        errors.append(f"최상위 응답이 JSON 객체(object)가 아닙니다 (실제 타입: {type(data).__name__}).")
        return errors

    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"필수 키 '{key}'가 없습니다.")

    if "suspected_cause" in data and not isinstance(data["suspected_cause"], str):
        errors.append(
            f"'suspected_cause'는 문자열이어야 하는데 {type(data['suspected_cause']).__name__}입니다."
        )

    for key in LIST_KEYS:
        if key not in data:
            continue
        value = data[key]
        if not isinstance(value, list):
            errors.append(f"'{key}'는 배열(list)이어야 하는데 {type(value).__name__}입니다.")
            continue
        for i, item in enumerate(value):
            if not isinstance(item, str):
                errors.append(f"'{key}[{i}]'는 문자열이어야 하는데 {type(item).__name__}입니다.")

    return errors


@dataclass
class ParsedResponse:
    """AI 응답 하나를 파싱한 결과. json_parsed/schema_valid가 모두 True여야
    analysis가 채워진다. 원본 텍스트(raw_response)는 항상 보존한다."""

    raw_response: str
    json_parsed: bool
    schema_valid: bool
    format_errors: List[str] = field(default_factory=list)
    analysis: Optional[AIAnalysis] = None


def parse_ai_response(raw_text: str) -> ParsedResponse:
    """AI의 원본 응답 문자열을 파싱하고 형식을 검사한다.

    실패해도 예외를 던지지 않는다 (AttributeError/TypeError 없음). 대신 어느 단계에서
    실패했는지(json_parsed, schema_valid)와 구체적인 오류 목록(format_errors)을 담은
    ParsedResponse를 반환하며, 원본 텍스트는 raw_response에 그대로 보존한다."""
    data, json_error = _extract_json(raw_text)
    if json_error:
        return ParsedResponse(
            raw_response=raw_text, json_parsed=False, schema_valid=False, format_errors=[json_error]
        )

    data = _normalize_keys(data)
    schema_errors = _validate_schema(data)
    if schema_errors:
        return ParsedResponse(
            raw_response=raw_text, json_parsed=True, schema_valid=False, format_errors=schema_errors
        )

    analysis = AIAnalysis(
        suspected_cause=data["suspected_cause"],
        referenced_log_ids=[_normalize_log_id(x) for x in data["referenced_log_ids"]],
        next_steps=list(data["next_steps"]),
        unknowns=list(data["unknowns"]),
        raw_response=raw_text,
    )
    return ParsedResponse(raw_response=raw_text, json_parsed=True, schema_valid=True, analysis=analysis)


@dataclass
class ValidationResult:
    parsed: ParsedResponse
    warnings: List[str] = field(default_factory=list)
    format_valid: bool = True
    existing_ids: List[str] = field(default_factory=list)
    missing_ids: List[str] = field(default_factory=list)

    @property
    def analysis(self) -> Optional[AIAnalysis]:
        return self.parsed.analysis

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


def validate(parsed: ParsedResponse, valid_log_ids: set) -> ValidationResult:
    """parsed.schema_valid가 False면 내용 검증을 하지 않고 형식 오류만 그대로 전달한다.
    schema_valid가 True인 경우에만 아래의 "내용 검증"(존재하지 않는 로그 ID, 근거 없음,
    과확신 표현, 빈 필드 등)을 수행한다."""
    if not parsed.schema_valid:
        return ValidationResult(parsed=parsed, warnings=list(parsed.format_errors), format_valid=False)

    analysis = parsed.analysis
    warnings: List[str] = []

    # 주의: 여기서 확인하는 것은 "AI가 인용한 log_id가 입력 로그 목록에 실제로 존재하는가" 뿐이다.
    # log_id가 존재한다는 것이 그 로그가 실제로 의심 원인을 입증한다는 뜻은 아니다.
    # 그 로그가 원인과 실제로 관련 있는지, 원인 분석 내용 자체가 맞는지는 사람이 직접 판단해야 한다.
    existing_ids = [lid for lid in analysis.referenced_log_ids if lid in valid_log_ids]
    hallucinated = [lid for lid in analysis.referenced_log_ids if lid not in valid_log_ids]
    if hallucinated:
        warnings.append(f"⚠ 존재하지 않는 로그 ID를 인용했습니다 (환각 의심): {hallucinated}")

    if not analysis.referenced_log_ids:
        warnings.append(
            "⚠ 참조한 로그 ID가 하나도 없습니다. 근거 없는 주장일 수 있으니 원인 서술을 그대로 믿지 마세요."
        )

    if not analysis.suspected_cause.strip():
        warnings.append("⚠ 의심 원인(suspected_cause)이 비어 있습니다.")

    if not analysis.next_steps:
        warnings.append("⚠ 다음 확인 방법(next_steps)이 비어 있습니다.")

    combined_text = analysis.suspected_cause + " ".join(analysis.next_steps) + " ".join(analysis.unknowns)
    found_phrases = [p for p in OVERCONFIDENT_PHRASES if p in combined_text]
    if found_phrases:
        warnings.append(
            f"⚠ AI가 과도하게 확신하는 표현을 사용했습니다: {found_phrases}. 원인이 확정된 것으로 오해하지 마세요."
        )

    if not analysis.unknowns:
        warnings.append(
            "⚠ '아직 모르는 것'을 하나도 제시하지 않았습니다. AI가 불확실성을 숨기고 있을 수 있습니다."
        )

    return ValidationResult(
        parsed=parsed,
        warnings=warnings,
        format_valid=True,
        existing_ids=existing_ids,
        missing_ids=hallucinated,
    )
