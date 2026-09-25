"""데이터 구조 정의 (dataclass)."""
from dataclasses import dataclass, field
from typing import List


@dataclass
class LogEntry:
    log_id: str
    timestamp: str
    level: str
    message: str


@dataclass
class IncidentInput:
    incident_id: str
    service_name: str
    status_summary: str
    logs: List[LogEntry]

    def valid_log_ids(self) -> set:
        return {log.log_id for log in self.logs}

    def to_prompt_text(self) -> str:
        lines = [
            f"장애 ID: {self.incident_id}",
            f"서비스명: {self.service_name}",
            f"현재 상태 요약: {self.status_summary}",
            "",
            "로그 목록 (log_id 는 절대 새로 만들지 말고, 아래 있는 것만 인용하세요):",
        ]
        for log in self.logs:
            lines.append(f"- [{log.log_id}] ({log.timestamp}, {log.level}) {log.message}")
        return "\n".join(lines)


@dataclass
class AIAnalysis:
    suspected_cause: str = ""
    referenced_log_ids: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    raw_response: str = ""
