import pytest
from fastapi.testclient import TestClient

from layer_a import CheckRequest, load_rule_pack, run_layer_a
from layer_a.contrast import contrast_ratio, parse_colour
from main import app

PACK = load_rule_pack()
client = TestClient(app)


def ids(text: str = "", **kw) -> list[str]:
    return [f.rule_id for f in run_layer_a(CheckRequest(text=text, **kw), PACK)]


# ---- contrast ----

def test_black_on_white_is_21():
    assert contrast_ratio("#000", "#ffffff") == pytest.approx(21.0, abs=0.01)


def test_grey_777_just_fails_aa():
    assert contrast_ratio("#777777", "#ffffff") == pytest.approx(4.48, abs=0.01)


def test_rgb_parsing():
    assert parse_colour("rgb(26, 86, 219)") == (26, 86, 219)


def test_large_text_uses_lower_threshold():
    # about 3.5:1 fails normal text but passes large text
    pair = {"element": "x", "foreground": "#8a8a8a", "background": "#ffffff"}
    assert "A11Y-001" in ids(colour_pairs=[{**pair, "large_text": False}])
    assert "A11Y-001" not in ids(colour_pairs=[{**pair, "large_text": True}])


# ---- terms ----

def test_banned_term_inflections():
    for word in ["guarantee", "guarantees", "Guaranteed", "guaranteeing"]:
        assert "BAN-001" in ids(f"We {word} it."), word


def test_banned_term_span_points_at_text():
    text = "Returns are guaranteed."
    f = next(f for f in run_layer_a(CheckRequest(text=text), PACK) if f.rule_id == "BAN-001")
    assert text[f.span.start : f.span.end] == "guaranteed"
    assert f.fix_type == "replace" and f.suggestion == "aims to deliver"


def test_no_match_inside_other_words():
    assert "BAN-004" not in ids("This is secure and accurate.")


def test_required_term_only_when_triggered():
    assert "REQ-001" in ids("Get a free account.")
    assert "REQ-001" not in ids("Get a free account. T&C apply.")
    assert "REQ-001" not in ids("Open an account today.")


def test_hyphenated_risk_free_does_not_trigger_free_offer():
    out = ids("A risk-free plan.")
    assert "BAN-002" in out and "REQ-001" not in out


# ---- tone ----

def test_exclamations():
    assert ids("Great!") == []
    assert ids("Great!!") == ["TONE-001"]


def test_shouting_ignores_allowed_acronyms():
    assert ids("Check SEBI rules and the BIGGEST news.") == ["TONE-002"]


# ---- alt text ----

def test_missing_alt_from_html():
    assert ids(html='<img src="a.png">') == ["A11Y-002"]


def test_decorative_empty_alt_is_fine():
    assert ids(html='<img src="a.png" alt="" role="presentation">') == []


def test_filename_alt_is_weak():
    assert ids(images=[{"src": "a.png", "alt": "DSC_1234"}]) == ["A11Y-003"]


# ---- API ----

def test_check_endpoint():
    r = client.post("/layer-a/check", json={"text": "100% safe and revolutionary!!"})
    assert r.status_code == 200
    body = r.json()
    assert body["rule_pack_version"] == PACK.version
    assert {f["rule_id"] for f in body["findings"]} == {"BAN-003", "BAN-007", "TONE-001"}
    assert body["counts"]["total"] == 3


def test_rule_pack_endpoint():
    r = client.get("/layer-a/rule-pack")
    assert r.status_code == 200 and r.json()["version"] == PACK.version
