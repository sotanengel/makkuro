from __future__ import annotations

import pytest

from makkuro.detectors.custom import CustomPatternDetector, make_custom_detectors


def test_basic_match():
    d = CustomPatternDetector(name="employee_id", pattern=r"EMP-\d{6}")
    hits = d.scan("see EMP-123456 in the report")
    assert len(hits) == 1
    assert hits[0].type == "EMPLOYEE_ID"
    assert hits[0].value == "EMP-123456"
    assert hits[0].detector == "employee_id"


def test_invalid_name_rejected():
    with pytest.raises(ValueError):
        CustomPatternDetector(name="bad name!", pattern=r".")


def test_invalid_pattern_fails_eagerly():
    with pytest.raises(ValueError):
        CustomPatternDetector(name="x", pattern=r"(unclosed")


def test_make_many():
    dets = make_custom_detectors(
        {
            "internal_token": r"TKN_[A-Z0-9]{4}",
            "ticket": r"TCK-\d+",
        }
    )
    assert {d.name for d in dets} == {"internal_token", "ticket"}
