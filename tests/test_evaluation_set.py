"""The evaluation dataset (>= 15 questions) must exist, be diverse, and every case must behave as expected."""
import json
import sys

import pytest

from app.config import ROOT

sys.path.insert(0, str(ROOT / "evaluation"))
import run_eval  # noqa: E402

CASES = json.loads((ROOT / "evaluation" / "questions.json").read_text())


def test_dataset_size_and_diversity():
    assert len(CASES) >= 15
    assert len({c["id"] for c in CASES}) == len(CASES)
    assert {"easy", "medium", "hard"} <= {c["difficulty"] for c in CASES}
    cats = {c["category"] for c in CASES}
    for needed in ("no_source", "poor_retrieval", "malformed", "unsupported_conclusion", "multi_source_conflict",
                   "historical_version", "failed_dependency", "outdated_secondary"):
        assert needed in cats
    assert {c.get("demo") for c in CASES} >= {"A", "B", "C", "D", "E"}


@pytest.fixture(scope="module")
def results():
    return {r["case"]["id"]: r for r in run_eval.run()}


@pytest.mark.parametrize("cid", [c["id"] for c in CASES])
def test_case_behaves_as_expected(results, cid):
    r = results[cid]
    assert r["passed"], r["problems"]
