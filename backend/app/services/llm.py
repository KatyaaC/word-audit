"""LLM clients and routing. Restricted content remains local. Commercial calls require confirmation and redaction."""
import json
import re
from typing import Optional

import httpx

from ..config import Settings, get_settings
from .redaction import redact_payload


class LLMError(Exception):
    pass


# Prompts
_JSON_ONLY = "Return ONLY a JSON object, no prose, no markdown fences."
PROMPTS = {
    "extract_claims": (
        "You extract factual marketing claims from text. A claim is any statement asserting a number, a result, a "
        "comparison, a superlative or a guarantee. Split each into parts. " + _JSON_ONLY +
        ' Schema: {"claims":[{"text":"exact sentence from the input","metric":"what is measured, short noun phrase",'
        '"value":number|null,"unit":"%|customer|day|x|..."|null,"qualifier":"up to|guaranteed|..."|null,'
        '"scope":"who/what it applies to"|null,"conditions":string|null,"period":"2025|Q3 2025|..."|null}]}',
        lambda p: p["text"],
    ),
    "explain": (
        "Rewrite the finding as a short, plain-language explanation for a marketer. Do not change, add or drop any "
        'number or fact. ' + _JSON_ONLY + ' Schema: {"explanation": string}',
        lambda p: json.dumps(p, ensure_ascii=False),
    ),
    "propose_fix": (
        "Rewrite the sentence minimally so it is fully supported by the approved fact. Use only numbers, qualifiers "
        "and scope found in the approved fact. Keep the creator's intent and tone. " + _JSON_ONLY +
        ' Schema: {"sentence": string}',
        lambda p: json.dumps(p, ensure_ascii=False),
    ),
    "interpret_rule": (
        "You are a content reviewer. State in one sentence how you interpret the brand rule, then for each sample "
        "snippet say whether it complies. " + _JSON_ONLY + ' Schema: {"interpretation": string, "verdicts": [bool]}',
        lambda p: json.dumps({"rule": p["rule_text"], "snippets": p.get("probes", [])}, ensure_ascii=False),
    ),
    "judge_conflict": (
        "Decide whether two brand rules can contradict each other (content that satisfies one must violate the "
        "other). " + _JSON_ONLY + ' Schema: {"conflict": bool, "reason": string}',
        lambda p: json.dumps({"rule_a": p["rule_a"], "rule_b": p["rule_b"]}, ensure_ascii=False),
    ),
}


def parse_json_text(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    a, b = raw.find("{"), raw.rfind("}")
    if a < 0 or b < a:
        raise LLMError("model did not return JSON")
    try:
        return json.loads(raw[a:b + 1])
    except json.JSONDecodeError as e:
        raise LLMError(f"invalid JSON from model: {e}") from e


# Clients
class AnthropicClient:
    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    def generate(self, task: str, payload: dict, temperature: float = 0.0) -> dict:
        system, build = PROMPTS[task]
        try:
            r = httpx.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": self.model, "max_tokens": 1500, "temperature": temperature, "system": system,
                      "messages": [{"role": "user", "content": build(payload)}]},
                timeout=60,
            )
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
        except httpx.HTTPError as e:
            raise LLMError(f"commercial API error: {e}") from e
        return parse_json_text(text)


class OllamaClient:
    def __init__(self, url: str, model: str):
        self.url, self.model = url.rstrip("/"), model

    def generate(self, task: str, payload: dict, temperature: float = 0.0) -> dict:
        system, build = PROMPTS[task]
        try:
            r = httpx.post(
                f"{self.url}/api/chat",
                json={"model": self.model, "stream": False, "format": "json", "options": {"temperature": temperature},
                      "messages": [{"role": "system", "content": system},
                                   {"role": "user", "content": build(payload)}]},
                timeout=180,
            )
            r.raise_for_status()
            text = r.json()["message"]["content"]
        except (httpx.HTTPError, KeyError) as e:
            raise LLMError(f"local model error: {e}") from e
        return parse_json_text(text)


_VAGUE = {"professional", "friendly", "appropriate", "modern", "clean", "engaging", "natural", "warm", "approachable",
          "premium", "authentic", "relevant", "suitable", "tasteful", "bold", "energetic", "formal", "casual"}


class MockClient:
    """Deterministic offline client for tests and local development."""

    model = "mock-local"

    def generate(self, task: str, payload: dict, temperature: float = 0.0) -> dict:
        from ..engine.claims import heuristic_extract

        if task == "extract_claims":
            return {"claims": [c.model_dump() for c in heuristic_extract(payload["text"])]}
        if task == "explain":
            return {"explanation": payload.get("template", "")}
        if task == "propose_fix":
            return {"sentence": payload.get("canonical") or payload.get("original", "")}
        if task == "interpret_rule":
            words = set(re.findall(r"[a-z]+", payload["rule_text"].lower()))
            vague = bool(words & _VAGUE)
            idx = int(payload.get("sample_index", 0))
            readings = ["strictly a formal register with no slang", "loosely anything that is not rude",
                        "whatever matches the brand voice sample deck"]
            interp = readings[idx % 3] if vague else payload["rule_text"]
            probes = payload.get("probes", [])
            verdicts = []
            for p in probes:
                base = (sum(map(ord, p)) % 2 == 0)
                verdicts.append(base ^ bool(vague and idx % 2))
            return {"interpretation": interp, "verdicts": verdicts}
        if task == "judge_conflict":
            a, b = payload["rule_a"].lower(), payload["rule_b"].lower()
            shared = (set(re.findall(r"[a-z]+", a)) & set(re.findall(r"[a-z]+", b))) - {
                "the", "a", "an", "use", "in", "of", "to", "and", "or", "with", "for", "all", "our"}
            pos = any(w in a for w in ("always", "must", "required"))
            neg = any(w in b for w in ("never", "must not", "do not", "avoid", "banned"))
            pos2 = any(w in b for w in ("always", "must", "required"))
            neg2 = any(w in a for w in ("never", "must not", "do not", "avoid", "banned"))
            conflict = len(shared) >= 2 and ((pos and neg) or (pos2 and neg2))
            return {"conflict": conflict, "reason": "opposite obligations on the same subject" if conflict else ""}
        raise LLMError(f"unknown task {task}")


# Router
class LLMRouter:
    def __init__(self, local, commercial=None):
        self.local, self.commercial = local, commercial
        self.calls = []

    def _log(self, task, provider, model, classification, redacted):
        self.calls.append({"task": task, "provider": provider, "model": model,
                           "classification": classification, "redacted": redacted})

    def will_use_external(self, classification: str, external_confirmed: bool) -> bool:
        return bool(self.commercial) and classification != "Restricted" and external_confirmed

    def preview_outbound(self, payload: dict, protected_terms=None) -> dict:
        return redact_payload(payload, protected_terms)

    def run(self, task: str, payload: dict, *, classification: str = "Internal", external_confirmed: bool = False,
            temperature: float = 0.0) -> dict:
        if self.will_use_external(classification, external_confirmed):
            try:
                out = self.commercial.generate(task, redact_payload(payload), temperature)
                self._log(task, "commercial", self.commercial.model, classification, True)
                return out
            except LLMError:
                pass  # fall back to the local model; never retry externally with unredacted text
        out = self.local.generate(task, payload, temperature)
        self._log(task, "local", self.local.model, classification, False)
        return out

    def reset_calls(self):
        self.calls = []

    def usage_summary(self) -> dict:
        providers, tasks, models = {}, {}, set()
        for c in self.calls:
            providers[c["provider"]] = providers.get(c["provider"], 0) + 1
            tasks[c["task"]] = tasks.get(c["task"], 0) + 1
            models.add(c["model"])
        return {"calls": len(self.calls), "providers": providers, "tasks": tasks, "models": sorted(models)}


def build_router(settings: Optional[Settings] = None) -> LLMRouter:
    s = settings or get_settings()
    local = OllamaClient(s.ollama_url, s.ollama_model) if s.local_llm_provider == "ollama" else MockClient()
    commercial = None
    if s.llm_provider == "anthropic" and s.anthropic_api_key:
        commercial = AnthropicClient(s.anthropic_api_key, s.commercial_model)
    return LLMRouter(local, commercial)
