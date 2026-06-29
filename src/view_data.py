"""把 jsonl 数据文件打印成人能读的样子(字段名一行,内容一行)。

jsonl 文件一行一条、挤在一起不好读;这个脚本只负责"美化显示",不改原文件。
对 legal_sft.jsonl(原始数据)和 scored.jsonl(打分结果)都能用。

用法:
    python src/view_data.py                                  # 默认看 legal_sft.jsonl 前 10 条
    python src/view_data.py --file data/processed/scored.jsonl
    python src/view_data.py --n 5                            # 只看前 5 条
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILE = ROOT / "data/processed/legal_sft.jsonl"


def main() -> None:
    p = argparse.ArgumentParser(description="美化查看 jsonl 数据")
    p.add_argument("--file", default=str(DEFAULT_FILE), help="要看的 jsonl 文件")
    p.add_argument("--n", type=int, default=10, help="看前 N 条(0=全部)")
    args = p.parse_args()

    if not Path(args.file).exists():
        sys.exit(f"找不到文件:{args.file}")

    lines = open(args.file, encoding="utf-8").read().splitlines()
    if args.n:
        lines = lines[: args.n]

    for i, line in enumerate(lines, 1):
        rec = json.loads(line)
        print(f"========== 第 {i} 条 ==========")
        for key, value in rec.items():          # 每个字段:字段名一行,内容一行
            print(key)
            print(value if value != "" else "(空)")
            print()


if __name__ == "__main__":
    main()
