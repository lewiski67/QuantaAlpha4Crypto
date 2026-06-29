from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict
from typing import Any, Protocol

import numpy as np
import pandas as pd

from quantaalpha_crypto.mining.proposal import (
    FactorProposalCandidate,
    FactorProposalContext,
    FactorProposalResult,
    FactorRepairContext,
    FactorRepairResult,
)

DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-8"
DEFAULT_ANTHROPIC_MAX_TOKENS = 64000
DEFAULT_ANTHROPIC_EFFORT = "max"
DEFAULT_ANTHROPIC_THINKING = {"type": "adaptive", "display": "omitted"}
CRYPTO_FACTOR_AVAILABLE_COLUMNS = [
    "futures_open",
    "futures_high",
    "futures_low",
    "futures_close",
    "futures_volume",
    "futures_quote_volume",
    "futures_trade_count",
    "futures_taker_buy_base_volume",
    "futures_taker_buy_quote_volume",
    "futures_funding_rate",
    "futures_mark_close",
    "futures_premium_close",
    "spot_open",
    "spot_high",
    "spot_low",
    "spot_close",
    "spot_volume",
    "spot_quote_volume",
    "spot_trade_count",
    "spot_taker_buy_base_volume",
    "spot_taker_buy_quote_volume",
]


class CompletionClient(Protocol):
    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        temperature: float | None,
        effort: str | None,
        thinking: dict[str, Any] | None,
        output_schema: dict[str, Any] | None = None,
    ) -> str | dict[str, Any]: ...


class AnthropicCompletionClient:
    def __init__(
        self,
        api_key: str | None = None,
        api_url: str = "https://api.anthropic.com/v1/messages",
        anthropic_version: str = "2023-06-01",
        timeout_seconds: int = 120,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.api_url = api_url
        self.anthropic_version = anthropic_version
        self.timeout_seconds = timeout_seconds

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        max_tokens: int,
        temperature: float | None,
        effort: str | None,
        thinking: dict[str, Any] | None,
        output_schema: dict[str, Any] | None = None,
    ) -> str:
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic crypto factor provider.")

        request_payload = {
            "model": model,
            "system": system_prompt,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if temperature is not None:
            request_payload["temperature"] = temperature
        output_config = {}
        if effort is not None:
            output_config["effort"] = effort
        if output_schema is not None:
            output_config["format"] = _anthropic_output_format(output_schema)
        if output_config:
            request_payload["output_config"] = output_config
        if thinking is not None:
            request_payload["thinking"] = thinking
        body = json.dumps(request_payload).encode("utf-8")
        request = urllib.request.Request(
            self.api_url,
            data=body,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": self.anthropic_version,
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")
            raise RuntimeError(f"Anthropic API request failed with HTTP {error.code}: {detail}") from error

        text = "".join(
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        )
        if text:
            return text
        content_types = [block.get("type") for block in payload.get("content", [])]
        raise RuntimeError(
            "Anthropic API response did not contain text output "
            f"(stop_reason={payload.get('stop_reason')!r}, content_types={content_types!r})."
        )


def _anthropic_output_format(output_schema: dict[str, Any]) -> dict[str, Any]:
    output_format = dict(output_schema)
    output_format.pop("name", None)
    return output_format


class AnthropicCryptoFactorProposalProvider:
    def __init__(
        self,
        completion_client: CompletionClient | None = None,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        max_tokens: int = DEFAULT_ANTHROPIC_MAX_TOKENS,
        temperature: float | None = None,
        effort: str | None = DEFAULT_ANTHROPIC_EFFORT,
        thinking: dict[str, Any] | None = DEFAULT_ANTHROPIC_THINKING,
    ) -> None:
        self.completion_client = completion_client or AnthropicCompletionClient()
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.effort = effort
        self.thinking = thinking

    def propose(self, context: FactorProposalContext) -> FactorProposalResult:
        response = self.completion_client.complete(
            system_prompt=_proposal_system_prompt(),
            user_prompt=_proposal_user_prompt(context),
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            effort=self.effort,
            thinking=self.thinking,
            output_schema=_proposal_output_schema(),
        )
        payload = _parse_llm_json(response)
        candidates = [_candidate_from_payload(item) for item in payload.get("candidates", [])]
        return FactorProposalResult(
            provider_name="anthropic",
            prompt_context={
                "prompt_template": "crypto_factor_proposal_v1",
                "output_schema": "crypto_factor_candidates_v1",
                "model": self.model,
                "max_tokens": self.max_tokens,
                "effort": self.effort,
                "thinking": self.thinking,
                "candidate_horizon": context.candidate_horizon,
                "rebalance_frequency": context.rebalance_frequency,
            },
            candidates=candidates,
            raw_response=response,
            parsed_response=payload,
        )


class AnthropicCryptoFactorRepairProvider:
    def __init__(
        self,
        completion_client: CompletionClient | None = None,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        max_tokens: int = DEFAULT_ANTHROPIC_MAX_TOKENS,
        temperature: float | None = None,
        effort: str | None = DEFAULT_ANTHROPIC_EFFORT,
        thinking: dict[str, Any] | None = DEFAULT_ANTHROPIC_THINKING,
    ) -> None:
        self.completion_client = completion_client or AnthropicCompletionClient()
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.effort = effort
        self.thinking = thinking

    def repair(self, context: FactorRepairContext) -> FactorRepairResult:
        response = self.completion_client.complete(
            system_prompt=_repair_system_prompt(),
            user_prompt=_repair_user_prompt(context),
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            effort=self.effort,
            thinking=self.thinking,
        )
        payload = _parse_llm_json(response)
        repaired_payload = payload.get("repaired_candidate")
        repaired_candidate = _candidate_from_payload(repaired_payload) if repaired_payload else None
        return FactorRepairResult(
            provider_name="anthropic",
            prompt_context={
                "repair_template": "crypto_factor_repair_v1",
                "output_schema": "crypto_factor_repair_v1",
                "model": self.model,
                "max_tokens": self.max_tokens,
                "effort": self.effort,
                "thinking": self.thinking,
                "attempt_number": context.attempt_number,
                "max_attempts": context.max_attempts,
                "rebalance_frequency": context.rebalance_frequency,
            },
            repaired_candidate=repaired_candidate,
            raw_response=response,
            parsed_response=payload,
        )


def _candidate_from_payload(payload: dict[str, Any]) -> FactorProposalCandidate:
    factor_name = str(payload["factor_name"])
    factor_callable_reference = str(payload.get("factor_callable_reference") or f"anthropic.{factor_name}")
    python_code = str(payload["python_code"])
    return FactorProposalCandidate(
        factor_name=factor_name,
        factor_callable_reference=factor_callable_reference,
        factor_callable=_compile_factor_callable(python_code),
        source_code=python_code,
    )


def _compile_factor_callable(python_code: str):
    namespace: dict[str, Any] = {
        "__builtins__": {
            "abs": abs,
            "bool": bool,
            "float": float,
            "int": int,
            "len": len,
            "max": max,
            "min": min,
            "pow": pow,
            "range": range,
            "sum": sum,
        },
        "np": np,
        "pd": pd,
    }
    exec(compile(python_code, "<llm_factor>", "exec"), namespace)  # noqa: S102
    factor = namespace.get("factor")
    if not callable(factor):
        raise ValueError("LLM factor code must define callable function `factor(data)`.")
    return factor


def _parse_llm_json(response: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    matches = re.findall(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", response)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue
    start = response.find("{")
    end = response.rfind("}")
    if start != -1 and end != -1 and start < end:
        return json.loads(response[start : end + 1])
    raise json.JSONDecodeError("Could not parse LLM JSON response.", response, 0)


def _proposal_system_prompt() -> str:
    return (
        "You generate research-only crypto directional factor candidates for Binance market data. "
        "Return only JSON. Do not include trading orders, live strategy instructions, or deployment advice."
    )


def _proposal_output_schema() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "factor_name": {"type": "string"},
                            "factor_callable_reference": {"type": "string"},
                            "python_code": {"type": "string"},
                        },
                        "required": ["factor_name", "factor_callable_reference", "python_code"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["candidates"],
            "additionalProperties": False,
        },
    }


def _proposal_user_prompt(context: FactorProposalContext) -> str:
    return json.dumps(
        {
            "task": "propose_crypto_directional_factor_candidates",
            "requirements": [
                "Each candidate must define Python code with exactly one function: factor(data).",
                "factor(data) must return a pandas Series indexed by timestamp and symbol.",
                "If research_direction is provided, every candidate must directly test that direction rather than generic momentum or reversal templates.",
                "Return 4 to 6 candidates.",
                "Do not include import statements. The execution environment already provides pandas as pd and numpy as np.",
                "Do not call __import__, eval, exec, open, subprocess, network APIs, filesystem APIs, or environment variable APIs.",
                "Use only historical/current rows available in data; do not use future information.",
                "Do not use centered rolling windows, negative shifts, or target/forward-return columns.",
                "Assume data is a MultiIndex pandas DataFrame with levels timestamp and symbol.",
                "Only reference columns from available_columns when reading data.",
            ],
            "available_columns": context.available_columns or CRYPTO_FACTOR_AVAILABLE_COLUMNS,
            "context": asdict(context),
            "output_schema": {
                "candidates": [
                    {
                        "factor_name": "string",
                        "factor_callable_reference": "string",
                        "python_code": "def factor(data): ...",
                    }
                ]
            },
        },
        indent=2,
        sort_keys=True,
        default=str,
    )


def _repair_system_prompt() -> str:
    return (
        "You repair research-only crypto directional factor Python code. "
        "Return only JSON. Preserve the no-future-information constraint."
    )


def _repair_user_prompt(context: FactorRepairContext) -> str:
    return json.dumps(
        {
            "task": "repair_crypto_directional_factor_candidate",
            "requirements": [
                "Return null if the candidate cannot be repaired safely.",
                "A repaired candidate must define exactly one function: factor(data).",
                "factor(data) must return a pandas Series indexed by timestamp and symbol.",
                "Preserve the original research_direction if one is provided.",
                "Do not include import statements. The execution environment already provides pandas as pd and numpy as np.",
                "Do not call __import__, eval, exec, open, subprocess, network APIs, filesystem APIs, or environment variable APIs.",
                "Use only historical/current rows available in data; do not use future information.",
                "Only reference columns from available_columns when reading data.",
            ],
            "available_columns": context.available_columns or CRYPTO_FACTOR_AVAILABLE_COLUMNS,
            "original_candidate": {
                "factor_name": context.original_candidate.factor_name,
                "factor_callable_reference": context.original_candidate.factor_callable_reference,
            },
            "diagnostic_reference": context.diagnostic_reference,
            "diagnostic": context.diagnostic,
            "context": {
                "run_id": context.run_id,
                "attempt_number": context.attempt_number,
                "max_attempts": context.max_attempts,
                "candidate_horizon": context.candidate_horizon,
                "evaluation_grid": context.evaluation_grid,
                "walk_forward_settings": context.walk_forward_settings,
                "feature_data_dependencies": context.feature_data_dependencies,
                "pnl_data_dependencies": context.pnl_data_dependencies,
                "input_lookback_window": context.input_lookback_window,
                "update_frequency": context.update_frequency,
                "rebalance_frequency": context.rebalance_frequency,
                "research_direction": context.research_direction,
                "available_columns": context.available_columns,
            },
            "output_schema": {
                "repaired_candidate": {
                    "factor_name": "string",
                    "factor_callable_reference": "string",
                    "python_code": "def factor(data): ...",
                }
            },
        },
        indent=2,
        sort_keys=True,
        default=str,
    )
