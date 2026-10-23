"""Generate docs/failure_matrix.md from app/fallbacks.py  (use --check to verify it is up to date)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.fallbacks import POLICY  # noqa: E402

rows = ["# Failure & safety matrix", "",
        "*Generated from `app/fallbacks.py` by `scripts/make_failure_matrix.py` - do not edit by hand.*", "",
        "Principle: **no evidence -> no fabricated conclusion -> explain limitation -> ask for missing information "
        "-> escalate when required.**", "",
        "| Code | Situation | Severity | What the system does | Escalate? |", "|---|---|---|---|---|"]
for p in POLICY.values():
    rows.append(f"| `{p.code.value}` | {p.situation} | {p.severity} | {p.behaviour} | {'yes' if p.escalate else 'no'} |")
rows += ["", "Severity meaning: `info` = shown, no effect on status; `warning` = status becomes `partial`, confidence "
         "is lowered; `blocking` = the run stops and **no conclusion is produced**.", ""]
text = "\n".join(rows)
target = ROOT / "docs" / "failure_matrix.md"
if "--check" in sys.argv:
    ok = target.exists() and target.read_text() == text
    print("up to date" if ok else "OUT OF DATE: run python scripts/make_failure_matrix.py")
    sys.exit(0 if ok else 1)
target.write_text(text)
print("wrote", target)
