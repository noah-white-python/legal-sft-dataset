"""中文法律 SFT 数据集构建流水线。

把原始问答数据(冷启动开源数据集 / 爬虫产出)处理成可直接用于 SFT 训练的
Alpaca 格式,并产出一份数据质量报告(README 表格里的数字就来自这里)。

流水线五步:
    加载 -> 清洗 -> 去重(精确 + MinHash 近似) -> 质量过滤 -> 格式化

用法:
    python src/build_dataset.py                      # 跑全量
    python src/build_dataset.py --sample 5000        # 先小样本验证
    python src/build_dataset.py --no-minhash         # 跳过近似去重(更快)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from hashlib import md5
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# Windows 控制台默认 GBK,打印中文/符号会崩,统一切到 utf-8
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/raw/seed_ShengbinYue__DISC-Law-SFT.csv"
OUT_JSONL = ROOT / "data/processed/legal_sft.jsonl"
OUT_REPORT = ROOT / "docs/quality_report.md"

# 质量过滤阈值
MIN_Q_LEN = 5        # 问题太短多半是噪声
MIN_A_LEN = 10       # 答案太短没信息量
MAX_A_LEN = 2000     # 答案过长多半是拼接/爬错
MIN_CN_RATIO = 0.5   # 中文字符占比下限(滤掉乱码/纯英文)

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WS_RE = re.compile(r"\s+")
_CN_RE = re.compile(r"[一-鿿]")


def clean_text(s: str) -> str:
    """单条文本清洗:全角->半角、去控制字符、压缩空白。"""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKC", s)   # 全角数字/字母/标点 -> 半角
    s = _CONTROL_RE.sub("", s)             # 去除不可见控制字符
    s = _WS_RE.sub(" ", s).strip()         # 多个空白压成一个
    return s


def cn_ratio(s: str) -> float:
    """中文字符占比,用于滤掉乱码和非中文样本。"""
    if not s:
        return 0.0
    return len(_CN_RE.findall(s)) / len(s)


def minhash_dedup(df: pd.DataFrame, threshold: float, num_perm: int = 64) -> pd.DataFrame:
    """MinHash + LSH 近似去重:删掉语义/字面高度重复但非完全相同的样本。

    精确去重只能抓到一字不差的重复;真实数据里大量是'改了标点/多了空格/
    抄来抄去'的近似重复,得靠 MinHash 这种局部敏感哈希才能在大数据量下高效抓出。
    """
    from datasketch import MinHash, MinHashLSH

    def shingles(text: str, k: int = 5) -> set[str]:
        # 中文用字符级 k-gram 作为'指纹片段'
        text = text.replace(" ", "")
        return {text[i : i + k] for i in range(max(len(text) - k + 1, 1))}

    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    keep = []
    for idx, text in tqdm(
        zip(df.index, df["_dedup_text"]), total=len(df), desc="MinHash 近似去重"
    ):
        m = MinHash(num_perm=num_perm)
        for sh in shingles(text):
            m.update(sh.encode("utf-8"))
        if lsh.query(m):          # 已存在近似样本 -> 丢弃
            continue
        lsh.insert(str(idx), m)
        keep.append(idx)
    return df.loc[keep]


def build(args: argparse.Namespace) -> None:
    report: list[str] = ["# 数据质量报告(自动生成)\n"]

    def log(line: str) -> None:
        print(line)
        report.append(line)

    # --- 1. 加载 ---
    if not Path(args.input).exists():
        sys.exit(f"找不到输入文件:{args.input}")
    df = pd.read_csv(args.input)
    df.columns = [c.lstrip("﻿") for c in df.columns]   # 去掉 BOM
    if args.sample:
        df = df.head(args.sample)
    raw_n = len(df)
    log(f"- 原始采集量:{raw_n} 条")

    # --- 2. 清洗 ---
    df["question"] = df["question"].map(clean_text)
    df["answer"] = df["answer"].map(clean_text)
    df = df[(df["question"] != "") & (df["answer"] != "")]
    after_clean = len(df)
    log(f"- 缺失/空值过滤后:{after_clean} 条(去掉 {raw_n - after_clean} 条空样本)")

    # --- 3a. 精确去重 ---
    df["_hash"] = (df["question"] + "\x01" + df["answer"]).map(
        lambda s: md5(s.encode("utf-8")).hexdigest()
    )
    df = df.drop_duplicates("_hash")
    after_exact = len(df)
    dup_rate = (after_clean - after_exact) / after_clean * 100 if after_clean else 0
    log(f"- 精确去重后:{after_exact} 条(精确重复率 {dup_rate:.1f}%)")

    # --- 3b. MinHash 近似去重 ---
    if args.no_minhash:
        after_near = after_exact
        log("- 近似去重:已跳过(--no-minhash)")
    else:
        df["_dedup_text"] = df["question"] + df["answer"]
        df = minhash_dedup(df, threshold=args.minhash_threshold)
        after_near = len(df)
        near_rate = (after_exact - after_near) / after_exact * 100 if after_exact else 0
        log(
            f"- MinHash 近似去重后:{after_near} 条"
            f"(阈值 {args.minhash_threshold},又删掉 {near_rate:.1f}% 近似重复)"
        )

    # --- 4. 质量过滤 ---
    q_len = df["question"].str.len()
    a_len = df["answer"].str.len()
    mask = (
        (q_len >= MIN_Q_LEN)
        & (a_len >= MIN_A_LEN)
        & (a_len <= MAX_A_LEN)
        & (df["answer"].map(cn_ratio) >= MIN_CN_RATIO)
    )
    df = df[mask]
    final_n = len(df)
    log(
        f"- 质量过滤后:{final_n} 条"
        f"(问≥{MIN_Q_LEN} 答 {MIN_A_LEN}-{MAX_A_LEN} 字、中文占比≥{MIN_CN_RATIO})"
    )

    # --- 统计 ---
    log(f"\n- **最终有效数据:{final_n} 条**")
    log(f"- 总有效率(最终/原始):{final_n / raw_n * 100:.1f}%")
    log(f"- 平均问题长度:{df['question'].str.len().mean():.0f} 字")
    log(f"- 平均答案长度:{df['answer'].str.len().mean():.0f} 字")

    # --- 5. 格式化为 Alpaca SFT 格式并落盘 ---
    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for q, a in zip(df["question"], df["answer"]):
            rec = {
                "instruction": q,
                "input": "",
                "output": a,
                "source": "DISC-Law-SFT",
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    log(f"\n- 已写出 Alpaca 格式训练数据:{OUT_JSONL.relative_to(ROOT)}")

    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"\n报告已保存:{OUT_REPORT.relative_to(ROOT)}")


def main() -> None:
    p = argparse.ArgumentParser(description="中文法律 SFT 数据集构建流水线")
    p.add_argument("--input", default=str(DEFAULT_INPUT), help="原始数据 CSV 路径")
    p.add_argument("--sample", type=int, default=0, help="只取前 N 条(调试用,0=全量)")
    p.add_argument("--no-minhash", action="store_true", help="跳过 MinHash 近似去重")
    p.add_argument("--minhash-threshold", type=float, default=0.8, help="近似去重相似度阈值")
    build(p.parse_args())


if __name__ == "__main__":
    main()
