import json
import urllib.request

import pytest
import pandas as pd

from quantaalpha_crypto.mining.llm_provider import (
    AnthropicCompletionClient,
    AnthropicCryptoFactorProposalProvider,
    AnthropicCryptoFactorRepairProvider,
    DEFAULT_ANTHROPIC_MODEL,
)
from quantaalpha_crypto.mining.proposal import FactorProposalCandidate, FactorProposalContext, FactorRepairContext


class FakeCompletionClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def complete(self, *, system_prompt, user_prompt, model, max_tokens, temperature, effort, thinking, output_schema=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "effort": effort,
                "thinking": thinking,
                "output_schema": output_schema,
            }
        )
        return self.response


def test_anthropic_proposal_provider_uses_opus_4_8_max_effort_by_default():
    client = FakeCompletionClient(
        {
            "candidates": [
                {
                    "factor_name": "momentum",
                    "factor_callable_reference": "llm.momentum",
                    "python_code": "def factor(data):\n    return data['close']",
                }
            ]
        }
    )

    provider = AnthropicCryptoFactorProposalProvider(completion_client=client)
    provider.propose(_proposal_context())

    assert DEFAULT_ANTHROPIC_MODEL == "claude-opus-4-8"
    assert client.calls[0]["model"] == "claude-opus-4-8"
    assert client.calls[0]["max_tokens"] == 64000
    assert client.calls[0]["effort"] == "max"
    assert client.calls[0]["thinking"] == {"type": "adaptive", "display": "omitted"}
    assert client.calls[0]["temperature"] is None


def test_anthropic_proposal_provider_requests_json_schema_output():
    client = FakeCompletionClient({"candidates": []})
    provider = AnthropicCryptoFactorProposalProvider(completion_client=client)

    provider.propose(_proposal_context())

    schema = client.calls[0]["output_schema"]
    assert schema["type"] == "json_schema"
    assert schema["schema"]["required"] == ["candidates"]
    candidate_schema = schema["schema"]["properties"]["candidates"]["items"]
    assert candidate_schema["required"] == ["factor_name", "factor_callable_reference", "python_code"]
    assert candidate_schema["additionalProperties"] is False


def test_anthropic_proposal_provider_parses_candidates_into_factor_callables():
    client = FakeCompletionClient(
        """```json
        {
          "candidates": [
            {
              "factor_name": "close_momentum",
              "factor_callable_reference": "llm.close_momentum",
              "python_code": "def factor(data):\\n    return data['close'].groupby(level='symbol').pct_change()"
            }
          ]
        }
        ```"""
    )

    provider = AnthropicCryptoFactorProposalProvider(completion_client=client, max_tokens=1234, temperature=0.2)
    result = provider.propose(_proposal_context())

    assert result.provider_name == "anthropic"
    assert result.prompt_context["model"] == "claude-opus-4-8"
    assert result.prompt_context["max_tokens"] == 1234
    assert result.prompt_context["effort"] == "max"
    assert result.prompt_context["thinking"] == {"type": "adaptive", "display": "omitted"}
    assert result.prompt_context["prompt_template"] == "crypto_factor_proposal_v1"
    assert result.prompt_context["output_schema"] == "crypto_factor_candidates_v1"
    assert [candidate.factor_name for candidate in result.candidates] == ["close_momentum"]
    assert result.candidates[0].factor_callable_reference == "llm.close_momentum"
    assert result.candidates[0].factor_callable(_panel_data()).dropna().iloc[0] == 1.0
    assert "ANTHROPIC_API_KEY" not in result.prompt_context


def test_anthropic_proposal_prompt_forbids_imports_and_lists_available_columns():
    client = FakeCompletionClient({"candidates": []})
    provider = AnthropicCryptoFactorProposalProvider(completion_client=client)

    provider.propose(_proposal_context())

    prompt = json.loads(client.calls[0]["user_prompt"])
    assert "available_columns" in prompt
    assert "futures_close" in prompt["available_columns"]
    assert "futures_funding_rate" in prompt["available_columns"]
    assert prompt["context"]["research_direction"] == "liquidity shock reversal"
    assert any("Do not include import statements" in item for item in prompt["requirements"])
    assert any("research_direction" in item for item in prompt["requirements"])
    assert any("__import__" in item for item in prompt["requirements"])


def test_anthropic_completion_client_merges_effort_and_json_schema_output(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _FakeHttpResponse({"content": [{"type": "text", "text": "{\"candidates\": []}"}]})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = AnthropicCompletionClient(api_key="test-key", timeout_seconds=321)

    response = client.complete(
        system_prompt="system",
        user_prompt="user",
        model="claude-opus-4-8",
        max_tokens=123,
        temperature=None,
        effort="max",
        thinking={"type": "adaptive", "display": "omitted"},
        output_schema={
            "type": "json_schema",
            "name": "crypto_factor_candidates_v1",
            "schema": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    )

    body = json.loads(captured["request"].data.decode("utf-8"))
    assert captured["timeout"] == 321
    assert body["output_config"]["effort"] == "max"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "name" not in body["output_config"]["format"]
    assert body["thinking"] == {"type": "adaptive", "display": "omitted"}
    assert response == "{\"candidates\": []}"


def test_anthropic_completion_client_reports_empty_text_response(monkeypatch):
    def fake_urlopen(request, timeout):
        return _FakeHttpResponse(
            {
                "stop_reason": "end_turn",
                "content": [{"type": "thinking", "thinking": "hidden"}],
            }
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = AnthropicCompletionClient(api_key="test-key")

    with pytest.raises(RuntimeError, match="stop_reason='end_turn'.*content_types=\\['thinking'\\]"):
        client.complete(
            system_prompt="system",
            user_prompt="user",
            model="claude-opus-4-8",
            max_tokens=123,
            temperature=None,
            effort="max",
            thinking={"type": "adaptive", "display": "omitted"},
        )


def test_anthropic_repair_provider_parses_repaired_candidate():
    client = FakeCompletionClient(
        {
            "repaired_candidate": {
                "factor_name": "fixed",
                "factor_callable_reference": "llm.fixed",
                "python_code": "def factor(data):\n    return -data['close']",
            }
        }
    )
    provider = AnthropicCryptoFactorRepairProvider(completion_client=client)

    result = provider.repair(
        FactorRepairContext(
            run_id="run_001",
            original_candidate=FactorProposalCandidate(
                factor_name="broken",
                factor_callable_reference="llm.broken",
                factor_callable=lambda data: data["close"],
            ),
            diagnostic_reference="rejected/broken.json",
            diagnostic={"error_type": "RuntimeError", "error_message": "boom"},
            attempt_number=1,
            max_attempts=2,
            candidate_horizon="1min",
            feature_data_dependencies=["fixture_spot_1m_ohlcv"],
            pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        )
    )

    assert result.provider_name == "anthropic"
    assert result.prompt_context["repair_template"] == "crypto_factor_repair_v1"
    assert result.prompt_context["max_tokens"] == 64000
    assert result.prompt_context["effort"] == "max"
    assert result.prompt_context["thinking"] == {"type": "adaptive", "display": "omitted"}
    assert result.repaired_candidate is not None
    assert result.repaired_candidate.factor_name == "fixed"
    assert result.repaired_candidate.factor_callable(_panel_data()).iloc[0] == -1.0


def test_anthropic_repair_prompt_forbids_imports_and_lists_available_columns():
    client = FakeCompletionClient({"repaired_candidate": None})
    provider = AnthropicCryptoFactorRepairProvider(completion_client=client)

    provider.repair(_repair_context())

    prompt = json.loads(client.calls[0]["user_prompt"])
    assert "available_columns" in prompt
    assert "futures_close" in prompt["available_columns"]
    assert "futures_mark_close" in prompt["available_columns"]
    assert prompt["context"]["research_direction"] == "liquidity shock reversal"
    assert any("Do not include import statements" in item for item in prompt["requirements"])
    assert any("research_direction" in item for item in prompt["requirements"])
    assert any("__import__" in item for item in prompt["requirements"])


def _repair_context():
    return FactorRepairContext(
        run_id="run_001",
        original_candidate=FactorProposalCandidate(
            factor_name="broken",
            factor_callable_reference="llm.broken",
            factor_callable=lambda data: data["close"],
        ),
        diagnostic_reference="rejected/broken.json",
        diagnostic={"error_type": "RuntimeError", "error_message": "boom"},
        attempt_number=1,
        max_attempts=2,
        candidate_horizon="1min",
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        research_direction="liquidity shock reversal",
    )


def _proposal_context():
    return FactorProposalContext(
        run_id="run_001",
        candidate_horizon="1min",
        feature_data_dependencies=["fixture_spot_1m_ohlcv"],
        pnl_data_dependencies=["fixture_spot_1m_ohlcv"],
        research_direction="liquidity shock reversal",
    )


def _panel_data():
    return pd.DataFrame(
        {"close": [1.0, 2.0]},
        index=pd.MultiIndex.from_tuples(
            [
                (pd.Timestamp("2026-01-01 00:00:00"), "BTCUSDT"),
                (pd.Timestamp("2026-01-01 00:01:00"), "BTCUSDT"),
            ],
            names=["timestamp", "symbol"],
        ),
    )


class _FakeHttpResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")
