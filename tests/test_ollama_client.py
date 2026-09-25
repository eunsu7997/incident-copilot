"""ollama_client.py에 대한 테스트.

이 파일은 제출 전 최종 점검에서 발견된 빈틈을 메우기 위해 추가됐다: call_ollama()의
예외 처리 경로(연결 실패, timeout, non-200 응답)가 그동안 실제 네트워크 호출로만
확인됐고 자동화된 테스트가 하나도 없었다. requests.post를 monkeypatch해서 실제
네트워크 없이 각 실패 경로가 OllamaError로 깔끔하게 변환되는지 확인한다.
"""
import requests
import pytest

from incident_copilot.ollama_client import call_ollama, OllamaError


class _FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text

    def json(self):
        return {"message": {"content": '{"suspected_cause": "x"}'}}


def test_call_ollama_connection_failure_raises_ollama_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr("incident_copilot.ollama_client.requests.post", _raise)
    with pytest.raises(OllamaError, match="연결할 수 없습니다"):
        call_ollama("llama3.2:1b", "프롬프트")


def test_call_ollama_timeout_raises_ollama_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr("incident_copilot.ollama_client.requests.post", _raise)
    with pytest.raises(OllamaError, match="timeout"):
        call_ollama("llama3.2:1b", "프롬프트", timeout=5)


def test_call_ollama_non_200_status_raises_ollama_error(monkeypatch):
    def _fake_post(*args, **kwargs):
        return _FakeResponse(status_code=500, text="internal error")

    monkeypatch.setattr("incident_copilot.ollama_client.requests.post", _fake_post)
    with pytest.raises(OllamaError, match="status=500"):
        call_ollama("llama3.2:1b", "프롬프트")
