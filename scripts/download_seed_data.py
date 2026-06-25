"""Day 2 成果线:从 HuggingFace 下载现成的中文法律问答数据集,作为项目冷启动的第一批数据。

设计要点:
- **走国内镜像 hf-mirror.com**:HuggingFace 官方域名在国内常不通,这里默认设置 HF_ENDPOINT。
- **列名自动探测**:不同数据集的字段名五花八门(question/instruction/input/问题...),
  脚本自动找出"问"列和"答"列,统一成 question / answer 两列存成 CSV。
- **失败可重试**:某个数据集下不动,不影响尝试列表里的下一个。

用法:
    python scripts/download_seed_data.py                 # 下载内置候选列表
    python scripts/download_seed_data.py 某用户/某数据集    # 指定一个数据集
    python scripts/download_seed_data.py 某数据集 --split train --limit 5000

下载完成后的 CSV 在 data/raw/ 下,可用 exercises/inspect_csv.py 检查质量。
"""

import os
import sys
import argparse
from itertools import islice
from pathlib import Path

# 关键:在 import datasets 之前设置镜像,否则不生效
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# Windows 控制台默认 GBK,强制 UTF-8 输出,避免打印中文/符号时崩
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd  # noqa: E402

# 候选中文法律问答数据集(从上到下依次尝试;某个不可用就换下一个)。
# 你在 Day 4 调研后可以把更合适的源加进来。
DEFAULT_DATASETS = [
    "ShengbinYue/DISC-Law-SFT",
    "Skepsun/lawyer_llama_data",
]

# 自动探测时,"问题列" / "答案列" 候选关键词(小写匹配)
QUESTION_KEYS = ["question", "instruction", "input", "query", "prompt", "问", "title"]
ANSWER_KEYS = ["answer", "output", "response", "completion", "content", "答", "text"]

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def pick_column(columns, candidates):
    """从 columns 里挑第一个命中 candidates 关键词的列名。"""
    lower = {c: str(c).lower() for c in columns}
    for key in candidates:
        for col, low in lower.items():
            if key in low:
                return col
    return None


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """把任意结构的问答数据,尽量统一成 question / answer 两列。"""
    q_col = pick_column(df.columns, QUESTION_KEYS)
    a_col = pick_column(df.columns, ANSWER_KEYS)

    if q_col is None or a_col is None or q_col == a_col:
        # 探测不出来就原样返回,让你人工看一眼列名再决定
        print(f"  [!] 无法自动识别问答列,保留原始列: {list(df.columns)}")
        return df

    out = pd.DataFrame({
        "question": df[q_col].astype(str).str.strip(),
        "answer": df[a_col].astype(str).str.strip(),
    })
    # 丢掉问或答为空的行
    out = out[(out["question"] != "") & (out["answer"] != "")]
    print(f"  识别到 问题列='{q_col}'  答案列='{a_col}'  -> 统一为 question/answer")
    return out


def download_one(name: str, split: str, limit: int | None) -> bool:
    """下载单个数据集并存成 CSV。成功返回 True。

    用 streaming 流式读取:只拉前 limit 条,既快又能绕过整库生成时的报错。
    """
    from datasets import load_dataset

    n = limit or 20000  # 不指定 limit 时,冷启动默认最多取 2 万条
    print(f"\n下载: {name}  (split={split}, 最多 {n} 条, 镜像={os.environ['HF_ENDPOINT']})")
    try:
        ds = load_dataset(name, split=split, streaming=True)
        rows = list(islice(ds, n))
    except Exception as e:
        print(f"  [FAIL] 失败: {e}")
        return False

    if not rows:
        print("  [FAIL] 数据集为空")
        return False

    df = pd.DataFrame(rows)
    df = normalize(df)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe = name.replace("/", "__")
    out_path = RAW_DIR / f"seed_{safe}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"  [OK] 已存 {len(df)} 条 -> {out_path}")
    print("  预览:")
    for _, row in df.head(2).iterrows():
        q = str(row.get("question", ""))[:60]
        a = str(row.get("answer", ""))[:60]
        print(f"    Q: {q}...")
        print(f"    A: {a}...")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="下载中文法律问答数据集(冷启动)")
    parser.add_argument("dataset", nargs="?", help="数据集名,如 用户名/数据集。不填则尝试内置候选列表")
    parser.add_argument("--split", default="train", help="数据划分,默认 train")
    parser.add_argument("--limit", type=int, default=None, help="只取前 N 条(先小规模试)")
    args = parser.parse_args()

    targets = [args.dataset] if args.dataset else DEFAULT_DATASETS

    any_ok = False
    for name in targets:
        if download_one(name, args.split, args.limit):
            any_ok = True
            if args.dataset:
                break  # 指定了具体数据集就只下这一个
            break  # 候选列表:下成一个就够冷启动了,够了就停

    if not any_ok:
        print("\n没有任何数据集下载成功。可能原因:")
        print("  1. 网络/镜像问题 —— 检查能否访问 https://hf-mirror.com")
        print("  2. 数据集名变了或需要登录 —— 去 hf-mirror.com 搜 '法律/legal' 换一个名字重试")
        print("  用法: python scripts/download_seed_data.py 用户名/数据集名 --limit 1000")
        sys.exit(1)


if __name__ == "__main__":
    main()
