"""cli.py 통합 테스트: 실제 run()을 호출해서 종료 코드와 저장된 결과 JSON까지 확인한다.

--offline-response 모드만 사용해서 실제 LLM 호출 없이(재현 가능하고 빠르게) 테스트한다.
pytest는 프로젝트 루트에서 실행한다고 가정한다(README의 실행 방법과 동일).

결과 파일은 실제 outputs/ 폴더가 아니라 매 테스트마다 pytest의 tmp_path(임시 폴더)에만
저장되도록 monkeypatch로 cli.OUTPUT_DIR을 바꿔치기한다 — 그래야 테스트를 반복 실행해도
outputs/ 폴더에 테스트용 파일이 쌓이지 않는다.
"""
import datetime as real_datetime
import json
from pathlib import Path

import pytest

from incident_copilot import cli

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def _isolate_output_dir(tmp_path, monkeypatch):
    """모든 테스트에서 cli.OUTPUT_DIR을 임시 폴더로 바꿔서, 실제 outputs/ 폴더(실행 증거가
    쌓이는 곳)를 건드리지 않도록 한다."""
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path)
    return tmp_path


def _result_files(incident_id: str):
    return sorted(cli.OUTPUT_DIR.glob(f"result_{incident_id}_*.json"))


def _latest_result_file(incident_id: str) -> Path:
    files = _result_files(incident_id)
    assert files, f"{incident_id}에 대한 결과 파일이 생성되지 않았습니다."
    return files[-1]


def test_cli_valid_offline_response_exits_zero_and_saves_expected_fields():
    fixture = FIXTURES_DIR / "valid_response.txt"
    exit_code = cli.run(["data/sample_incident_1.json", "--offline-response", str(fixture)])
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
    exit_code = cli.run(["data/sample_incident_1.json", "--offline-response", str(fixture)])
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


def test_same_second_consecutive_runs_keep_separate_files_with_preserved_raw_responses(monkeypatch):
    """같은 incident_id를 같은 초(timestamp 문자열 기준)에 연속 실행해도 결과 파일이
    서로 덮어쓰이지 않고 2개 모두 남아야 하며, 각각의 원본 응답도 서로 구분되어 보존돼야 한다.
    실제로 같은 초에 두 번 실행되는 상황을 재현하기 위해 datetime.now()를 고정값으로
    monkeypatch한다(타이밍에 의존하지 않는 결정적 테스트)."""
    fixed_now = real_datetime.datetime(2026, 1, 1, 0, 0, 0)

    class _FixedDateTime:
        @staticmethod
        def now():
            return fixed_now

    monkeypatch.setattr(cli.datetime, "datetime", _FixedDateTime)

    exit_code_1 = cli.run(
        ["data/sample_incident_1.json", "--offline-response", str(FIXTURES_DIR / "valid_response.txt")]
    )
    exit_code_2 = cli.run(
        ["data/sample_incident_1.json", "--offline-response", str(FIXTURES_DIR / "valid_response_alt.txt")]
    )
    assert exit_code_1 == 0
    assert exit_code_2 == 0

    files = _result_files("INC-2026-0001")
    assert len(files) == 2, f"같은 초에 실행한 결과가 파일 2개로 남아야 하는데 {len(files)}개다: {files}"
    # 파일명에 타임스탬프가 똑같이 박히므로(now()를 고정했으므로), 서로 다른 파일로 남았다는
    # 것 자체가 UUID 등 별도 구분자가 실제로 동작한다는 증거다.
    assert files[0].name != files[1].name

    contents = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    raw_responses = {c["raw_llm_response"].strip() for c in contents}
    assert len(raw_responses) == 2, "두 실행의 원본 응답이 서로 다르게, 둘 다 보존되어야 한다."
    for c in contents:
        assert c["processing_status"]["schema_valid"] is True
        assert c["parsed_analysis"] is not None
