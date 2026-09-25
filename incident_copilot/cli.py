"""명령줄(CLI, Command Line Interface) 진입점.

사용법: python run.py data/sample_incident_1.json

종료 코드(exit code):
  0 = 응답을 받았고, 형식 검사(JSON 파싱 + 스키마)까지 정상 통과함
      (내용 경고가 있어도 0 — 형식은 맞다는 뜻일 뿐 내용까지 정확하다는 뜻은 아님)
  1 = LLM 응답 자체를 받지 못함 (네트워크/Ollama 오류)
  2 = 응답은 받았지만 형식 검사(JSON 파싱 또는 스키마)에 실패함
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

from .data_loader import load_incident
from .ollama_client import call_ollama, OllamaError
from .validator import parse_ai_response, validate

DEFAULT_MODEL = "llama3.2:1b"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AI Incident Copilot - 장애 로그를 넣으면 AI가 의심 원인/근거/다음 확인 방법/모르는 것을 제시합니다."
    )
    parser.add_argument("incident_file", help="장애 입력 JSON 파일 경로 (예: data/sample_incident_1.json)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"사용할 Ollama 모델 이름 (기본값: {DEFAULT_MODEL})")
    parser.add_argument("--no-llm", action="store_true", help="LLM을 호출하지 않고 입력 로그 검증 로직만 테스트합니다.")
    parser.add_argument(
        "--offline-response",
        help=(
            "실제 LLM을 호출하지 않고, 이 경로의 텍스트 파일을 'AI 응답'으로 간주해서 "
            "검증 로직(형식 검사, 존재하지 않는 로그 ID 경고 등)만 실제로 실행해 봅니다. "
            "데모/테스트 용도이며, 이 옵션을 쓰면 실제 LLM 실행 결과가 아니라는 점을 화면과 결과 파일에 표시합니다."
        ),
    )
    return parser


def run(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)
    is_offline_replay = bool(args.offline_response)

    incident = load_incident(args.incident_file)
    prompt_text = incident.to_prompt_text()

    print("=" * 60)
    print(f"[입력 장애] {incident.incident_id} - {incident.service_name}")
    print(f"상태 요약: {incident.status_summary}")
    print(f"로그 {len(incident.logs)}건 (아래는 가상 데이터입니다)")
    print("=" * 60)

    if args.no_llm:
        print("--no-llm 옵션이 켜져 있어 실제 LLM 호출을 하지 않았습니다.")
        return 0

    if is_offline_replay:
        model_label = f"OFFLINE-REPLAY:{args.offline_response}"
        print(
            f"\n[알림] --offline-response 옵션 사용 중: 실제 LLM을 호출하지 않습니다.\n"
            f"아래 결과는 '{args.offline_response}'에 사람이 미리 작성해 둔 예시 응답을 "
            f"검증 로직에 통과시킨 것이며, 실제 LLM 실행 결과가 아닙니다 (검증 로직 데모용)."
        )
        raw_response = Path(args.offline_response).read_text(encoding="utf-8")
    else:
        model_label = args.model
        print(f"\nOllama 모델 호출 중... (model={args.model})")
        try:
            raw_response = call_ollama(args.model, prompt_text)
        except OllamaError as e:
            print(f"\n[실패] LLM 응답을 받지 못했습니다:\n{e}")
            _save_result(
                incident.incident_id,
                args.model,
                prompt_text,
                response_received=False,
                json_parsed=False,
                schema_valid=False,
                format_errors=[str(e)],
                analysis=None,
                warnings=[],
                raw_response=None,
                is_offline_replay=False,
            )
            return 1

    parsed = parse_ai_response(raw_response)

    if not parsed.schema_valid:
        stage = "JSON 파싱" if not parsed.json_parsed else "형식(스키마) 검사"
        print(f"\n[형식 오류] AI 응답이 {stage}을 통과하지 못했습니다. 원인 분석 내용을 신뢰할 수 없습니다.")
        for err in parsed.format_errors:
            print(f"  - {err}")
        print("\n원본 응답(raw_response)은 결과 파일에 그대로 보존됩니다.")
        _save_result(
            incident.incident_id,
            model_label,
            prompt_text,
            response_received=True,
            json_parsed=parsed.json_parsed,
            schema_valid=False,
            format_errors=parsed.format_errors,
            analysis=None,
            warnings=[],
            raw_response=raw_response,
            is_offline_replay=is_offline_replay,
        )
        return 2

    result = validate(parsed, incident.valid_log_ids())
    analysis = parsed.analysis

    print("\n--- AI 분석 결과 ---")
    print(f"[의심 원인]\n{analysis.suspected_cause}")
    print(f"\n[참조한 로그 ID]\n{analysis.referenced_log_ids}")
    print(f"\n[다음 확인 방법]")
    for i, step in enumerate(analysis.next_steps, 1):
        print(f"  {i}. {step}")
    print(f"\n[아직 모르는 것]")
    for i, unk in enumerate(analysis.unknowns, 1):
        print(f"  {i}. {unk}")

    total_refs = len(analysis.referenced_log_ids)
    print("\n--- 검증 결과 (이 프로그램이 자동으로 확인한 것) ---")
    print(
        f"[참조 ID 존재 확인] {len(result.existing_ids)}/{total_refs}개가 실제 입력 로그에 존재함"
        + (f", 존재하지 않는 ID: {result.missing_ids}" if result.missing_ids else "")
    )
    print(
        "  -> 주의: 이건 'ID가 입력 로그 목록에 있는가'만 자동으로 확인한 것입니다. "
        "그 로그가 실제로 의심 원인을 뒷받침하는지, 원인 분석 내용이 정확한지는 검사하지 않습니다."
    )
    print("[원인 판단] AI의 추정일 뿐이며, 실제로 맞는지는 사람이 로그 내용을 읽고 직접 검토해야 합니다.")

    if result.has_warnings():
        print("\n--- 추가 검증 경고 (내용 관련, 형식 오류 아님) ---")
        for w in result.warnings:
            print(f"  {w}")

    _save_result(
        incident.incident_id,
        model_label,
        prompt_text,
        response_received=True,
        json_parsed=True,
        schema_valid=True,
        format_errors=[],
        analysis=analysis,
        warnings=result.warnings,
        raw_response=raw_response,
        is_offline_replay=is_offline_replay,
        existing_ids=result.existing_ids,
        missing_ids=result.missing_ids,
    )
    return 0


def _save_result(
    incident_id,
    model,
    prompt_text,
    response_received,
    json_parsed,
    schema_valid,
    format_errors,
    analysis,
    warnings,
    raw_response,
    is_offline_replay,
    existing_ids=None,
    missing_ids=None,
):
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"result_{incident_id}_{timestamp}.json"
    payload = {
        "incident_id": incident_id,
        "model_used": model,
        "response_source": "offline_replay (사람이 작성한 예시 응답 — 실제 LLM 호출 아님)"
        if is_offline_replay
        else "ollama (실제 LLM 호출)",
        "generated_at": timestamp,
        "processing_status": {
            "response_received": response_received,
            "json_parsed": json_parsed,
            "schema_valid": schema_valid,
            "format_errors": format_errors or [],
            "note": (
                "response_received/json_parsed/schema_valid가 모두 true여야 아래 parsed_analysis와 "
                "id_existence_check가 의미가 있다. schema_valid가 true라는 것은 '형식이 스펙에 맞다'는 "
                "뜻일 뿐이며, 원인 분석 내용이 정확하다는 뜻은 아니다."
            ),
        },
        "prompt_sent_to_llm": prompt_text,
        "raw_llm_response": raw_response,
        "parsed_analysis": None
        if analysis is None
        else {
            "suspected_cause": analysis.suspected_cause,
            "referenced_log_ids": analysis.referenced_log_ids,
            "next_steps": analysis.next_steps,
            "unknowns": analysis.unknowns,
        },
        "validation_warnings": warnings or [],
        "id_existence_check": None
        if not schema_valid
        else {
            "existing_ids": existing_ids or [],
            "missing_ids": missing_ids or [],
            "note": (
                "이 항목은 'AI가 인용한 log_id가 입력 로그 목록에 실제로 있는가'만 확인한 것이다. "
                "그 로그가 의심 원인을 실제로 입증하는지, 원인 분석이 정확한지는 이 검사와 무관하며 "
                "사람이 직접 판단해야 한다."
            ),
        },
        "note": "이 결과는 참고용이며, 최종 원인 판단과 조치는 사람이 직접 확인해야 합니다.",
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장됨: {out_path}")
    return out_path


if __name__ == "__main__":
    sys.exit(run())
