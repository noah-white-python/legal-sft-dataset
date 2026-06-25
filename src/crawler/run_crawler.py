"""主爬虫(Day 5 同步版 + Day 6 进度监控)—— 把 storage / fetcher / parsers 串起来。

完整链路:
  生成待爬 URL → 跳过已爬过的(断点续爬)→ 逐个请求(带重试)
  → 成功就解析入库(自动去重)→ 失败就写死信 → tqdm 显示进度 → 每批打印汇总

运行(在项目根目录):
    python -m src.crawler.run_crawler --site quotes
    python -m src.crawler.run_crawler --site quotes --limit 3      # 只爬前 3 页试试
    python -m src.crawler.run_crawler --site baidu                 # 需先在 parsers.py 填好

断点续爬演示:跑一次,再跑一次 —— 第二次会显示"全部已爬过,跳过"。
想从头来就删掉 data/crawl.sqlite。
"""

import sys
import argparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")  # tqdm 进度条走 stderr,也要设
except Exception:
    pass

from tqdm import tqdm

# 兼容两种启动方式:python -m src.crawler.run_crawler 或直接 python run_crawler.py
try:
    from .storage import Storage
    from .fetcher import Fetcher
    from .parsers import SITES
except ImportError:
    from storage import Storage
    from fetcher import Fetcher
    from parsers import SITES


def crawl(site_key: str, limit: int | None, delay: float):
    if site_key not in SITES:
        print(f"未知站点 '{site_key}',可选:{list(SITES)}")
        sys.exit(1)

    parser = SITES[site_key]()
    storage = Storage()
    fetcher = Fetcher(max_retries=3, delay=delay)

    # 1) 生成待爬 URL
    pages = parser.list_pages()
    if limit:
        pages = pages[:limit]

    # 2) 断点续爬:扣掉已经处理过的 URL
    seen = storage.seen_urls()
    todo = [u for u in pages if u not in seen]
    print(f"站点={site_key}  总页 {len(pages)}  已处理 {len(pages) - len(todo)}  待爬 {len(todo)}")
    if not todo:
        print("全部已爬过,跳过。(想重爬就删 data/crawl.sqlite)")
        _summary(storage)
        return

    saved_total = 0
    ok_pages = 0
    dead_pages = 0

    # 3) 逐页爬,tqdm 显示进度条(已爬/总数/速度/预计剩余)
    for i, url in enumerate(tqdm(todo, desc="爬取中", unit="页"), start=1):
        try:
            html = fetcher.get(url)            # 带重试;到底失败会抛异常
            records = parser.parse(html, url)
            n = storage.save_records(url, records, parser.SOURCE)
            saved_total += n
            ok_pages += 1
        except Exception as e:
            # 重试用尽:进死信表,绝不让单页失败拖垮整轮
            storage.save_dead(url, f"{type(e).__name__}: {e}")
            dead_pages += 1

        # Day 6:每 5 页(或结束时)打印一行汇总
        if i % 5 == 0 or i == len(todo):
            tqdm.write(f"  进度 {i}/{len(todo)}:成功页 {ok_pages} / 死信页 {dead_pages} / 新增记录 {saved_total}")

    print(f"\n本轮完成:成功页 {ok_pages}、死信页 {dead_pages}、新增问答 {saved_total} 条")
    _summary(storage)
    storage.close()


def _summary(storage: Storage):
    s = storage.stats()
    print(f"数据库现状:有效记录 {s['records']} 条,死信 {s['dead_letters']} 条 "
          f"(库文件 data/crawl.sqlite)")


def main():
    ap = argparse.ArgumentParser(description="同步爬虫:断点续爬 + 去重 + 重试 + 死信 + 进度")
    ap.add_argument("--site", default="quotes", help="站点:quotes(演示) / baidu(待填)")
    ap.add_argument("--limit", type=int, default=None, help="只爬前 N 页(先小规模试错)")
    ap.add_argument("--delay", type=float, default=1.0, help="每次请求后睡几秒(限速护 IP)")
    args = ap.parse_args()
    crawl(args.site, args.limit, args.delay)


if __name__ == "__main__":
    main()
