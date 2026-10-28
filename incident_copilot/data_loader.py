"""장애 입력 JSON 파일을 읽어 IncidentInput 객체로 변환."""
import json
from pathlib import Path

from .models import IncidentInput, LogEntry


def load_incident(path: str) -> IncidentInput:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    logs = [
        LogEntry(
            log_id=item["log_id"],
            timestamp=item["timestamp"],
            level=item["level"],
            message=item["message"],
        )
        for item in data["logs"]
    ]
    _check_logs(logs)
    return IncidentInput(
        incident_id=data["incident_id"],
        service_name=data["service_name"],
        status_summary=data["status_summary"],
        logs=logs,
    )


def _check_logs(logs) -> None:
    """로그 ID가 비어 있거나 중복이면 ValueError를 낸다.

    ID가 중복되면 "AI가 인용한 ID가 실제로 있는가" 검증이 어느 로그를 가리키는지 모호해진다.
    """
    seen = set()
    for i, log in enumerate(logs):
        if not str(log.log_id).strip():
            raise ValueError(f"{i}번째 로그의 log_id가 비어 있습니다.")
        if not str(log.message).strip():
            raise ValueError(f"로그 {log.log_id}의 message가 비어 있습니다.")
        if log.log_id in seen:
            raise ValueError(f"log_id가 중복됩니다: {log.log_id}")
        seen.add(log.log_id)
