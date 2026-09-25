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
    return IncidentInput(
        incident_id=data["incident_id"],
        service_name=data["service_name"],
        status_summary=data["status_summary"],
        logs=logs,
    )
