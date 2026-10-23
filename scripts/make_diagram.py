"""Draw docs/architecture.png (needs matplotlib)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

steps = [
    ("INPUT", "POST /research  /analyze\nquestion + jurisdiction + as-of date + facts", "#e8eef7"),
    ("QUESTION ANALYSIS", "valid? jurisdiction, date, topics,\nfacts, 'predict-my-case' intent", "#fdf3d8"),
    ("RESEARCH", "discovery -> validation (source readable &\nunchanged?) -> quality gate -> primary > secondary", "#fdf3d8"),
    ("RETRIEVAL", "BM25 over section-level chunks\n(optional embedding rerank)", "#fdf3d8"),
    ("VERSION RESOLUTION", "amends / supersedes / clarifies, in force on\nas-of date?, outdated?, conflicts", "#fde4d8"),
    ("EVIDENCE", "verbatim quotes + character offsets,\nre-verified against the live file", "#dff3e3"),
    ("ANALYSIS", "structured template; labels VERIFIED / DERIVED /\nINTERPRETATION / UNCERTAIN ... (extractive or guarded LLM)", "#dff3e3"),
    ("RESPONSE", "answer, evidence, sources, version notes, limitations,\nconfidence, review flag, trace_id", "#e8eef7"),
]
fig, ax = plt.subplots(figsize=(9, 12))
ax.set_xlim(0, 10); ax.set_ylim(0, 24); ax.axis("off")
y = 22.6
for i, (t, d, col) in enumerate(steps):
    ax.add_patch(FancyBboxPatch((1.2, y - 1.0), 7.6, 2.0, boxstyle="round,pad=0.05,rounding_size=0.25",
                                fc=col, ec="#444", lw=1.2))
    ax.text(5, y + 0.45, t, ha="center", va="center", fontsize=12, fontweight="bold")
    ax.text(5, y - 0.35, d, ha="center", va="center", fontsize=9)
    if i < len(steps) - 1:
        ax.annotate("", xy=(5, y - 1.55), xytext=(5, y - 1.05), arrowprops=dict(arrowstyle="-|>", lw=1.6, color="#444"))
    y -= 2.7
ax.text(9.6, 12, "Any step can stop the run:\nNO EVIDENCE -> NO CONCLUSION\n-> limitation + next step", rotation=90,
        ha="center", va="center", fontsize=9, color="#a33")
ax.set_title("Legal Intelligence backend - architecture", fontsize=14, fontweight="bold")
out = Path(__file__).resolve().parent.parent / "docs" / "architecture.png"
fig.savefig(out, dpi=130, bbox_inches="tight")
print("wrote", out)
