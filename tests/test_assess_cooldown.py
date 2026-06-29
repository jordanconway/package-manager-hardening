# SPDX-FileCopyrightText: 2026 The Linux Foundation
#
# SPDX-License-Identifier: MIT

"""Unit tests for the cross-cutting assess_cooldown()."""

import audit


def _report(*, exclude_newer=None, dependabot_cooldown=None, detected=("python",)):
    """Build a minimal report dict for the cooldown assessment.

    exclude_newer / dependabot_cooldown are bools keyed implicitly to python
    via the report shape below.
    """
    report = {"ecosystems_detected": list(detected)}
    if "python" in detected:
        report["python"] = {"uv_config": {"exclude_newer": "7 days" if exclude_newer else None}}
    dep_status = "pass" if dependabot_cooldown else "warn"
    report["dependabot"] = {
        "ecosystems": {
            eco: {"status": dep_status, "cooldown_configured": bool(dependabot_cooldown)} for eco in detected
        }
    }
    return report


# ---------------------------------------------------------------------------
# auto strategy
# ---------------------------------------------------------------------------

def test_auto_dependabot_only_passes():
    r = _report(exclude_newer=False, dependabot_cooldown=True)
    result = audit.assess_cooldown(r, ["python"], strategy="auto")
    assert result["status"] == "pass"
    assert result["ecosystems"]["python"]["status"] == "pass"
    assert result["ecosystems"]["python"]["dependabot_cooldown"] is True
    assert result["ecosystems"]["python"]["resolver_level"] is False


def test_auto_resolver_only_passes():
    r = _report(exclude_newer=True, dependabot_cooldown=False)
    result = audit.assess_cooldown(r, ["python"], strategy="auto")
    assert result["ecosystems"]["python"]["status"] == "pass"


def test_auto_both_present_warns_with_conflict_note():
    r = _report(exclude_newer=True, dependabot_cooldown=True)
    result = audit.assess_cooldown(r, ["python"], strategy="auto")
    assert result["status"] == "warn"
    eco = result["ecosystems"]["python"]
    assert eco["status"] == "warn"
    assert "security-update exception" in eco["note"]
    assert "exclude-newer in [tool.uv]" in eco["note"]
    # overall section carries a summary note for the report renderer
    assert "note" in result


def test_auto_neither_fails():
    r = _report(exclude_newer=False, dependabot_cooldown=False)
    result = audit.assess_cooldown(r, ["python"], strategy="auto")
    assert result["status"] == "fail"
    assert "No release-age cooldown" in result["ecosystems"]["python"]["note"]


# ---------------------------------------------------------------------------
# dependabot strategy (lfreleng org posture)
# ---------------------------------------------------------------------------

def test_dependabot_strategy_dependabot_only_passes():
    r = _report(exclude_newer=False, dependabot_cooldown=True)
    result = audit.assess_cooldown(r, ["python"], strategy="dependabot")
    assert result["ecosystems"]["python"]["status"] == "pass"


def test_dependabot_strategy_flags_redundant_resolver():
    r = _report(exclude_newer=True, dependabot_cooldown=True)
    result = audit.assess_cooldown(r, ["python"], strategy="dependabot")
    eco = result["ecosystems"]["python"]
    assert eco["status"] == "warn"
    assert "redundant" in eco["note"]
    assert "automated security updates" in eco["note"]


def test_dependabot_strategy_missing_dependabot_fails_even_with_resolver():
    r = _report(exclude_newer=True, dependabot_cooldown=False)
    result = audit.assess_cooldown(r, ["python"], strategy="dependabot")
    assert result["ecosystems"]["python"]["status"] == "fail"


# ---------------------------------------------------------------------------
# resolver strategy
# ---------------------------------------------------------------------------

def test_resolver_strategy_resolver_present_passes():
    r = _report(exclude_newer=True, dependabot_cooldown=False)
    result = audit.assess_cooldown(r, ["python"], strategy="resolver")
    assert result["ecosystems"]["python"]["status"] == "pass"


def test_resolver_strategy_missing_resolver_fails():
    r = _report(exclude_newer=False, dependabot_cooldown=True)
    result = audit.assess_cooldown(r, ["python"], strategy="resolver")
    assert result["ecosystems"]["python"]["status"] == "fail"


# ---------------------------------------------------------------------------
# Scope: only native-cooldown ecosystems; none detected -> no section
# ---------------------------------------------------------------------------

def test_non_native_ecosystem_excluded():
    r = {
        "ecosystems_detected": ["go"],
        "dependabot": {"ecosystems": {"go": {"status": "pass", "cooldown_configured": True}}},
    }
    assert audit.assess_cooldown(r, ["go"], strategy="auto") is None


def test_mixed_detected_only_assesses_native():
    r = _report(exclude_newer=True, dependabot_cooldown=True, detected=("python", "go"))
    result = audit.assess_cooldown(r, ["python", "go"], strategy="auto")
    assert set(result["ecosystems"]) == {"python"}


def test_dependabot_file_absent_is_handled():
    # When dependabot.yml is absent, audit_dependabot emits string "missing"
    # values rather than dicts — must not crash.
    r = {
        "ecosystems_detected": ["python"],
        "python": {"uv_config": {"exclude_newer": "7 days"}},
        "dependabot": {"status": "missing", "ecosystems": {"python": "missing"}},
    }
    result = audit.assess_cooldown(r, ["python"], strategy="auto")
    # resolver present, dependabot absent -> pass under auto
    assert result["ecosystems"]["python"]["status"] == "pass"
    assert result["ecosystems"]["python"]["dependabot_cooldown"] is False


# ---------------------------------------------------------------------------
# nodejs / rust resolver detection
# ---------------------------------------------------------------------------

def test_nodejs_resolver_detected_from_minimum_release_age():
    r = {
        "ecosystems_detected": ["nodejs"],
        "nodejs": {"minimum_release_age": {"configured": True}},
        "dependabot": {"ecosystems": {"nodejs": {"status": "warn", "cooldown_configured": False}}},
    }
    result = audit.assess_cooldown(r, ["nodejs"], strategy="auto")
    assert result["ecosystems"]["nodejs"]["resolver_level"] is True
    assert result["ecosystems"]["nodejs"]["status"] == "pass"


def test_rust_resolver_detected_from_cargo_cooldown():
    r = {
        "ecosystems_detected": ["rust"],
        "rust": {"cooldown": {"configured": True}},
        "dependabot": {"ecosystems": {"rust": {"status": "pass", "cooldown_configured": True}}},
    }
    result = audit.assess_cooldown(r, ["rust"], strategy="auto")
    assert result["ecosystems"]["rust"]["status"] == "warn"  # both present
