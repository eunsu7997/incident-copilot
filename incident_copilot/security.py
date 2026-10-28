"""운영 환경에서 신뢰할 수 없는 입력을 다루기 위한 보안 보조 함수.

1. safe_filename_part — 입력값(incident_id)을 결과 파일 이름에 넣기 전에 안전한 문자만 남긴다.
   `../`나 `/`가 들어와도 outputs/ 폴더 밖으로 파일이 써지지 않게 하기 위함이다.
2. mask_sensitive — 로그에 섞여 있을 수 있는 민감정보(토큰, 비밀번호, 이메일, IP 등)를
   LLM에 보내기 전과 결과 파일에 저장하기 전에 가린다.

정규식 기반이라 모든 민감정보를 잡는다고 보장하지 않는다. 자주 나오는 형태를 줄이는 1차 방어선이다.
"""
import re
from typing import Dict, Tuple

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")
_MAX_FILENAME_PART = 64

# (이름, 패턴, 바꿀 문자열). 위에서부터 순서대로 적용한다.
# 키=값 형태를 이메일·IP보다 먼저 처리해야 "password=1.2.3.4" 같은 값도 통째로 가려진다.
_MASK_RULES = [
    (
        "secret_kv",
        re.compile(
            r"(?i)\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?key|token)\b(\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|\S+)"
        ),
        r"\1\2[MASKED]",
    ),
    ("bearer", re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [MASKED]"),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[MASKED_TOKEN]"),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[MASKED_TOKEN]"),
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "[MASKED_TOKEN]"),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[MASKED_EMAIL]"),
    ("ipv4", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"), "[MASKED_IP]"),
]


def safe_filename_part(value) -> str:
    """파일 이름에 넣어도 안전한 문자열로 바꾼다.

    영문자·숫자·`.`·`_`·`-`만 남기고 나머지는 `_`로 바꾼다. 앞의 점은 지워서 숨김 파일이나
    `..`가 되지 않게 하고, 너무 길면 자른다. 남는 게 없으면 "incident"를 쓴다.
    """
    cleaned = _SAFE_CHARS.sub("_", str(value)).lstrip(".")[:_MAX_FILENAME_PART]
    return cleaned or "incident"


def mask_sensitive(text) -> Tuple[str, Dict[str, int]]:
    """text 안의 민감정보를 가리고 (가린 문자열, 규칙별로 가린 개수)를 반환한다.

    None이 들어오면 그대로 (None, {})를 반환한다.
    """
    if text is None:
        return None, {}
    counts: Dict[str, int] = {}
    for name, pattern, replacement in _MASK_RULES:
        text, n = pattern.subn(replacement, text)
        if n:
            counts[name] = counts.get(name, 0) + n
    return text, counts
