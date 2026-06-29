"""用大模型给法律 SFT 数据打质量分(LLM-as-judge)。

请 DeepSeek 当"评委",对每条问答从三个维度打 1-5 分:
    复杂度(complexity)、清晰度(clarity)、信息量(informativeness)
输出带分数的新文件 + 一份平均分小结。

API key 从环境变量 DEEPSEEK_API_KEY 读取(不写进代码、不进 git)。

用法:
    python src/score_quality.py --sample 20      # 先小样本验证 prompt
    python src/score_quality.py --sample 1000     # 小批量
    python src/score_quality.py                    # 全量(慎用,要花钱)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import requests
from tqdm import tqdm

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/processed/legal_sft.jsonl"
DEFAULT_OUTPUT = ROOT / "data/processed/scored.jsonl"

API_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"

# 打分 prompt:要求模型严格输出 JSON,方便程序解析
SCORE_PROMPT = """你是一名严格的法律数据质量评审。请对下面这条"法律问答"从三个维度打分(1-5 分,5 最好):
- complexity:问题的专业性/复杂度(越是真实、有难度的法律问题分越高)
- clarity:答案表达是否清晰、有条理
- informativeness:答案信息量是否充足、是否真正解决问题

只输出一个 JSON,不要任何多余文字,格式:
{{"complexity": 整数, "clarity": 整数, "informativeness": 整数, "reason": "一句话理由"}}

【问题】{question}
【答案】{answer}"""


def score_one(record: dict, api_key: str, retries: int = 3) -> dict:
    """给单条数据打分,返回原记录 + 分数字段。

    失败会自动重试(应对网络抖动/限流);重试用完仍失败则标记 _error。
    """
    prompt = SCORE_PROMPT.format(
        question=record["instruction"], answer=record["output"][:1500]
    )
    last_err = ""
    for attempt in range(retries):
        try:
            resp = requests.post(
                API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,                       # 打分要稳定,设 0
                    "response_format": {"type": "json_object"},  # 强制返回 JSON
                },
                timeout=60,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            scores = json.loads(content)
            return {**record, **scores}
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(2 * (attempt + 1))   # 等一会儿再重试,越失败等越久
    return {**record, "_error": last_err}


def main() -> None:
    p = argparse.ArgumentParser(description="LLM-as-judge 数据质量打分")
    p.add_argument("--input", default=str(DEFAULT_INPUT), help="待打分的 jsonl")
    p.add_argument("--output", default=str(DEFAULT_OUTPUT), help="输出 jsonl")
    p.add_argument("--sample", type=int, default=0, help="只打前 N 条(0=全量)")
    p.add_argument("--workers", type=int, default=5, help="并发数")
    p.add_argument("--overwrite", action="store_true", help="忽略已有结果,从头重打(会重复花钱)")
    args = p.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        sys.exit("没找到环境变量 DEEPSEEK_API_KEY,请先设置 API key。")

    # 读数据
    records = [json.loads(line) for line in open(args.input, encoding="utf-8")]
    if args.sample:
        records = records[: args.sample]

    # 断点续跑:输出文件已存在,就跳过已打过分的(省钱,不重复打)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    done_keys = set()
    if out.exists() and not args.overwrite:
        for line in open(out, encoding="utf-8"):
            row = json.loads(line)
            if "_error" not in row:          # 失败的不算完成,留待重跑补打
                done_keys.add(row.get("instruction"))
    todo = [r for r in records if r["instruction"] not in done_keys]
    print(f"总 {len(records)} 条,已完成 {len(done_keys)} 条,本次要打 {len(todo)} 条,并发 {args.workers}")
    if not todo:
        print("全部已打分,无需再跑。")
        return

    # 并发打分 + 边跑边存(每完成一条立刻写盘,中断也不丢已完成的)
    mode = "w" if args.overwrite else "a"
    lock = Lock()  # 多线程同时写一个文件,加锁防止写串行
    with open(out, mode, encoding="utf-8") as f, ThreadPoolExecutor(args.workers) as pool:
        futures = [pool.submit(score_one, r, api_key) for r in todo]
        for fut in tqdm(as_completed(futures), total=len(todo), desc="打分中"):
            r = fut.result()
            with lock:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
                f.flush()

    # 小结:读完整输出文件统计
    all_rows = [json.loads(line) for line in open(out, encoding="utf-8")]
    ok = [r for r in all_rows if "_error" not in r]
    failed = len(all_rows) - len(ok)
    print(f"\n累计成功 {len(ok)} 条,失败 {failed} 条 -> {out.name}")
    if failed:
        print("(失败的可重新跑一次本命令,会自动只补打失败/未打的)")
    if ok:
        for dim in ("complexity", "clarity", "informativeness"):
            avg = sum(r.get(dim, 0) for r in ok) / len(ok)
            print(f"  平均 {dim}:{avg:.2f}")


if __name__ == "__main__":
    main()
