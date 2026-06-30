"""把打过分的法律 SFT 数据集上传到 HuggingFace Hub。

- 读 scored.jsonl(带质量分),切分 train/test,推送为一个数据集
- token 从环境变量 HF_TOKEN 读取(不写进代码、不进 git)

用法:
    python scripts/push_to_hf.py --repo 你的用户名/chinese-legal-sft
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from datasets import Dataset, DatasetDict

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SCORED = ROOT / "data/processed/scored.jsonl"
KEEP_FIELDS = ["instruction", "input", "output", "source",
               "complexity", "clarity", "informativeness"]


def main() -> None:
    p = argparse.ArgumentParser(description="上传法律 SFT 数据集到 HuggingFace")
    p.add_argument("--repo", required=True, help="目标仓库,如 用户名/chinese-legal-sft")
    p.add_argument("--test-size", type=int, default=500, help="测试集条数")
    args = p.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("没找到环境变量 HF_TOKEN,请先设置 HuggingFace write token。")
    if not SCORED.exists():
        sys.exit(f"找不到 {SCORED}")

    # 读数据,只留打分成功的,只保留需要的字段
    rows = []
    for line in open(SCORED, encoding="utf-8"):
        r = json.loads(line)
        if "_error" in r:
            continue
        rows.append({k: r.get(k) for k in KEEP_FIELDS})
    print(f"有效数据 {len(rows)} 条")

    # 切分 train/test
    ds = Dataset.from_list(rows).shuffle(seed=42)
    split = ds.train_test_split(test_size=args.test_size, seed=42)
    dd = DatasetDict({"train": split["train"], "test": split["test"]})
    print(f"train {len(dd['train'])} 条 / test {len(dd['test'])} 条")

    # 推送
    print(f"正在上传到 https://huggingface.co/datasets/{args.repo} ...")
    dd.push_to_hub(args.repo, token=token)
    print("上传完成!")


if __name__ == "__main__":
    main()
