"""把数据集和打分结果画成图,存到 docs/images/,供 README 引用。

画四张图:
    1. 三个质量维度的分数分布(柱状图)
    2. 综合分分布
    3. 问题长度分布(直方图)
    4. 答案长度分布(直方图)

用法:
    python src/visualize.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

sys.stdout.reconfigure(encoding="utf-8")

# matplotlib 默认不显示中文(变方框),指定中文字体解决
matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False   # 负号正常显示

ROOT = Path(__file__).resolve().parents[1]
SCORED = ROOT / "data/processed/scored.jsonl"
IMG_DIR = ROOT / "docs/images"

DIMS = {"complexity": "复杂度", "clarity": "清晰度", "informativeness": "信息量"}


def main() -> None:
    if not SCORED.exists():
        sys.exit(f"找不到打分文件 {SCORED},请先跑 score_quality.py")
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    rows = [json.loads(l) for l in open(SCORED, encoding="utf-8")]
    ok = [r for r in rows if "_error" not in r]
    print(f"读到 {len(ok)} 条有效打分数据")

    # --- 图1:三维度分数分布(并排柱状图)---
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, (key, label) in zip(axes, DIMS.items()):
        dist = Counter(r[key] for r in ok if isinstance(r.get(key), (int, float)))
        scores = [1, 2, 3, 4, 5]
        counts = [dist.get(s, 0) for s in scores]
        ax.bar(scores, counts, color="#4C72B0")
        avg = sum(s * c for s, c in zip(scores, counts)) / sum(counts)
        ax.set_title(f"{label}分布(平均 {avg:.2f})")
        ax.set_xlabel("分数")
        ax.set_ylabel("条数")
        ax.set_xticks(scores)
    fig.suptitle("LLM-as-judge 三维度质量分布(n=%d)" % len(ok), fontsize=14)
    fig.tight_layout()
    fig.savefig(IMG_DIR / "score_dist.png", dpi=120)
    plt.close(fig)

    # --- 图2:综合分分布 ---
    comp = [
        (r["complexity"] + r["clarity"] + r["informativeness"]) / 3
        for r in ok
        if all(isinstance(r.get(d), (int, float)) for d in DIMS)
    ]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(comp, bins=20, color="#55A868", edgecolor="white")
    ax.axvline(4, color="red", linestyle="--", label="高质量线 (≥4)")
    high = sum(1 for c in comp if c >= 4)
    ax.set_title(f"综合质量分布(高质量 {high} 条,占 {high/len(comp)*100:.1f}%)")
    ax.set_xlabel("综合分(三维平均)")
    ax.set_ylabel("条数")
    ax.legend()
    fig.tight_layout()
    fig.savefig(IMG_DIR / "overall_dist.png", dpi=120)
    plt.close(fig)

    # --- 图3/4:问题、答案长度分布 ---
    q_len = [len(r["instruction"]) for r in ok]
    a_len = [len(r["output"]) for r in ok]
    for data, name, fname, color in [
        (q_len, "问题", "qlen_dist.png", "#C44E52"),
        (a_len, "答案", "alen_dist.png", "#8172B3"),
    ]:
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.hist(data, bins=50, color=color, edgecolor="white")
        ax.set_title(f"{name}长度分布(平均 {sum(data)/len(data):.0f} 字)")
        ax.set_xlabel("字符数")
        ax.set_ylabel("条数")
        fig.tight_layout()
        fig.savefig(IMG_DIR / fname, dpi=120)
        plt.close(fig)

    print(f"已生成 4 张图 -> {IMG_DIR.relative_to(ROOT)}/")
    for f in ("score_dist.png", "overall_dist.png", "qlen_dist.png", "alen_dist.png"):
        print(f"  - {f}")


if __name__ == "__main__":
    main()
