"""AI 응답 파싱 및 검증.

이 모듈이 하는 일 (사람이 반드시 확인해야 하는 부분):
1. AI가 낸 JSON 텍스트를 파싱한다.
2. AI가 인용한 log_id가 실제 입력 로그에 존재하는지 검사한다 (존재하지 않으면 경고 = "환각/hallucination" 의심).
3. 근거(참조 로그)가 하나도 없는데 원인을 말했으면 경고한다.
4. 과도하게 확신하는 표현("확실", "틀림없이", "100%", "분명히")을 쓰면 경고한다.
"""
import json
import re
from dataclasses import dataclass, field
from typing import List

from .models import AIAnalysis

OVERCONFIDENT_PHRASES = ["확실히", "틀림없이", "100%", "명백히", "당연히", "확정적으로"]


def _normalize_log_id(value) -> str:
    """모델이 로그 ID를 '[LOG-101]'처럼 대괄호를 붙여 내보내는 경우가 있어(프롬프트에
    로그를 "- [LOG-101] ..." 형태로 보여줬기 때문에 그대로 따라 적는 것으로 보임),
    실제 ID 존재 여부를 비교하기 전에 대괄호와 앞뒤 공백을 제거해 정규화한다."""
    return str(value).strip().strip("[]").strip()


@dataclass
class ValidationResult:
    analysis: AIAnalysis
    warnings: List[str] = field(default_factory=list)
    parse_ok: bool = True
    existing_ids: List[str] = field(default_factory=list)
    missing_ids: List[str] = field(default_factory=list)

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


def parse_ai_response(raw_text: str) -> AIAnalysis:
    """AI의 원본 응답 문자열에서 JSON 부분을 추출해 AIAnalysis로 변환한다."""
    text = raw_text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return AIAnalysis(
                suspected_cause="(파싱 실패: AI가 JSON 형식을 지키지 않았습니다)",
                raw_response=raw_text,
            )
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return AIAnalysis(
                suspected_cause="(파싱 실패: AI가 JSON 형식을 지키지 않았습니다)",
                raw_response=raw_text,
            )

    # 작은 모델(예: llama3.2:1b)이 가끔 키 앞뒤에 공백을 붙여서 내보내는 경우가 있어
    # (예: " suspected_cause") 키를 strip() 해서 정규화한다.
    if isinstance(data, dict):
        data = {(k.strip() if isinstance(k, str) else k): v for k, v in data.items()}

    return AIAnalysis(
        suspected_cause=str(data.get("suspected_cause", "")),
        referenced_log_ids=[_normalize_log_id(x) for x in (data.get("referenced_log_ids", []) or [])],
        next_steps=list(data.get("next_steps", []) or []),
        unknowns=list(data.get("unknowns", []) or []),
        raw_response=raw_text,
    )


def validate(analysis: AIAnalysis, valid_log_ids: set) -> ValidationResult:
    warnings: List[str] = []
    parse_ok = "파싱 실패" not in analysis.suspected_cause

    if not parse_ok:
        warnings.append("AI 응답을 JSON으로 해석하지 못했습니다. raw_response를 직접 확인하세요.")
        return ValidationResult(analysis=analysis, warnings=warnings, parse_ok=False)

    # 주의: 여기서 확인하는 것은 "AI가 인용한 log_id가 입력 로그 목록에 실제로 존재하는가" 뿐이다.
    # log_id가 존재한다는 것이 그 로그가 실제로 의심 원인을 입증한다는 뜻은 아니다.
    # 그 로그가 원인과 실제로 관련 있는지는 사람이 로그 내용을 읽고 직접 판단해야 한다.
    existing_ids = [lid for lid in analysis.referenced_log_ids if lid in valid_log_ids]
    hallucinated = [lid for lid in analysis.referenced_log_ids if lid not in valid_log_ids]
    if hallucinated:
        warnings.append(
            f"⚠ 존재하지 않는 로그 ID를 인용했습니다 (환각 의심): {hallucinated}"
        )

    if not analysis.referenced_log_ids:
        warnings.append(
            "⚠ 참조한 로그 ID가 하나도 없습니다. 근거 없는 주장일 수 있으니 원인 서술을 그대로 믿지 마세요."
        )

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
        analysis=analysis,
        warnings=warnings,
        parse_ok=True,
        existing_ids=existing_ids,
        missing_ids=hallucinated,
    )
