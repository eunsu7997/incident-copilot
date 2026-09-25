"""cli.py 통합 테스트: 실제 run()을 호출해서 종료 코드와 저장된 결과 JSON까지 확인한다.

--offline-response 모드만 사용해서 실제 LLM 호출 없이(재현 가능하고 빠르게) 테스트한다.
pytest는 프로젝트 루트에서 실행한다고 가정한다(README의 실행 방법과 동일).
"""
import json
from pathlib import Path

from incident_copilot.cli import run, OUTPUT_DIR

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _latest_result_file(incident_id: str) -> Path:
    files = sorted(OUTPUT_DIR.glob(f"result_{incident_id}_*.json"))
    assert files, f"{incident_id}에 대한 결과 파일이 생성되지 않았습니다."
    return files[-1]


def test_cli_valid_offline_response_exits_zero_and_saves_expected_fields():
    fixture = FIXTURES_DIR / "valid_response.txt"
    exit_code = run(["data/sample_incident_1.json", "--offline-response", str(fixture)])
    assert exit_code == 0

    result_path = _latest_result_file("INC-2026-0001")
    data = json.loads(result_path.read_text(encoding="utf-8"))

    assert data["processing_status"]["response_received"] is True
    assert data["processing_status"]["json_parsed"] is True
    assert data["processing_status"]["schema_valid"] is True
    assert data["response_source"].startswith("offline_replay")
    assert data["parsed_analysis"] is not None
    assert data["id_existence_check"] is not None
    assert set(data["id_existence_check"]["existing_ids"]) == {"LOG-002", "LOG-007"}


def test_cli_malformed_offline_response_exits_nonzero_and_records_format_errors():
    """AI 응답이 'null'이면(형식 오류) 종료 코드는 0이 아니어야 하고, success처럼 보이는
    필드가 없어야 하며, 원본 응답은 그대로 결과 파일에 남아야 한다."""
    fixture = FIXTURES_DIR / "malformed_response_null.txt"
    exit_code = run(["data/sample_incident_1.json", "--offline-response", str(fixture)])
    assert exit_code == 2

    result_path = _latest_result_file("INC-2026-0001")
    data = json.loads(result_path.read_text(encoding="utf-8"))

    assert data["processing_status"]["response_received"] is True
    assert data["processing_status"]["json_parsed"] is True
    assert data["processing_status"]["schema_valid"] is False
    assert data["processing_status"]["format_errors"]
    assert data["parsed_analysis"] is None
    assert data["id_existence_check"] is None
    assert data["raw_llm_response"].strip() == "null"
