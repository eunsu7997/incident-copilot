"""명령줄(CLI, Command Line Interface) 진입점.

사용법: python run.py data/sample_incident_1.json
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
    return parser


def run(argv=None) -> int:
    args = build_arg_parser().parse_args(argv)

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

    print(f"\nOllama 모델 호출 중... (model={args.model})")
    try:
        raw_response = call_ollama(args.model, prompt_text)
    except OllamaError as e:
        print(f"\n[실패] LLM 호출 중 오류가 발생했습니다:\n{e}")
        _save_result(incident.incident_id, args.model, prompt_text, None, [str(e)], success=False)
        return 1

    analysis = parse_ai_response(raw_response)
    result = validate(analysis, incident.valid_log_ids())

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
        "그 로그가 실제로 의심 원인을 뒷받침하는지는 검사하지 않습니다."
    )
    print("[원인 판단] AI의 추정일 뿐이며, 실제로 맞는지는 사람이 로그 내용을 읽고 직접 검토해야 합니다.")

    if result.has_warnings():
        print("\n--- 추가 검증 경고 ---")
        for w in result.warnings:
            print(f"  {w}")

    _save_result(
        incident.incident_id,
        args.model,
        prompt_text,
        analysis,
        result.warnings,
        success=True,
        raw_response=raw_response,
        existing_ids=result.existing_ids,
        missing_ids=result.missing_ids,
    )
    return 0


def _save_result(
    incident_id,
    model,
    prompt_text,
    analysis,
    warnings,
    success,
    raw_response=None,
    existing_ids=None,
    missing_ids=None,
):
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = OUTPUT_DIR / f"result_{incident_id}_{timestamp}.json"
    payload = {
        "incident_id": incident_id,
        "model_used": model,
        "generated_at": timestamp,
        "success": success,
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
        "validation_warnings": warnings,
        "id_existence_check": {
            "existing_ids": existing_ids or [],
            "missing_ids": missing_ids or [],
            "note": "이 항목은 'AI가 인용한 log_id가 입력 로그 목록에 실제로 있는가'만 확인한 것이다. "
            "그 로그가 의심 원인을 실제로 입증하는지는 이 검사와 무관하며 사람이 직접 판단해야 한다.",
        },
        "note": "이 결과는 참고용이며, 최종 원인 판단과 조치는 사람이 직접 확인해야 합니다.",
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장됨: {out_path}")


if __name__ == "__main__":
    sys.exit(run())
