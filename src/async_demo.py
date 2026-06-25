"""Day 3 学习线:亲手写异步 —— 并发请求一批 URL,并把并发数控制住。

对应计划里的循序渐进 4 步:
  1. 只请求 1 个 URL 的异步函数,跑通
  2. asyncio.gather 同时请求 5 个,感受比同步快
  3. 加 asyncio.Semaphore 限制并发,请求一批
  4. 每个请求加 try/except,记录成功/失败 + 耗时

运行:
    python src/async_demo.py

目标站是 books.toscrape.com —— 专门给人练爬虫的合规沙盒,随便抓。

读代码时重点看三个注释标了 ★ 的地方,那是异步的命门。
"""

import sys
import time
import asyncio

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import aiohttp

# 这个站有 50 页书目,正好拿来做"一批 URL"
BASE = "https://books.toscrape.com/catalogue/page-{}.html"
URLS = [BASE.format(i) for i in range(1, 51)]  # 50 个 URL


# ---- 第 1 步:请求 1 个 URL 的异步函数 --------------------------------------
async def fetch_one(session: aiohttp.ClientSession, url: str) -> tuple[str, int, float]:
    """请求单个 URL,返回 (url, 状态码或-1, 耗时秒)。

    ★ 关键点 1:async 函数里要用异步库 aiohttp,不能用同步的 requests。
       如果这里写成 requests.get(),整个程序会退化成同步,一点都不快。
    """
    t0 = time.perf_counter()
    try:
        # ★ 关键点 2:await 那一刻,控制权才让给 event loop 去跑别的请求。
        #   "等服务器响应" 这段时间,柜员(event loop)被释放去叫下一个客户。
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            await resp.text()  # 把响应体读完也要 await
            return url, resp.status, time.perf_counter() - t0
    except Exception as e:
        # Day 1 学的 try/except:一个请求失败不该拖垮整批
        print(f"  [失败] {url}: {type(e).__name__}: {e}")
        return url, -1, time.perf_counter() - t0


# ---- 第 3 步:用 Semaphore 限制并发 ----------------------------------------
async def fetch_with_limit(
    session: aiohttp.ClientSession, sem: asyncio.Semaphore, url: str
):
    """信号量 = 发 N 张通行证,拿到证才能发请求,发完还证。永远最多 N 个在飞。

    为什么限并发:一次性把 50/1000 个请求全发出去,① 你网络扛不住;
    ② 对方会当你是攻击直接封 IP。所以要给并发数设上限。
    """
    async with sem:  # 没拿到通行证就在这儿排队等
        return await fetch_one(session, url)


# ---- 第 4 步:把一批 URL 并发跑完,统计成功/失败/耗时 ------------------------
async def main():
    concurrency = 10  # ★ 关键点 3:同时最多 10 个请求在飞,这是限流的核心参数
    sem = asyncio.Semaphore(concurrency)

    print(f"异步并发抓取 {len(URLS)} 个页面,并发上限 {concurrency} ...")
    t0 = time.perf_counter()

    async with aiohttp.ClientSession() as session:
        # asyncio.gather:把一堆协程一次性丢给 event loop,"并发地跑,都跑完告诉我"
        tasks = [fetch_with_limit(session, sem, url) for url in URLS]
        results = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - t0
    ok = [r for r in results if r[1] == 200]
    fail = [r for r in results if r[1] != 200]
    avg = sum(r[2] for r in results) / len(results)

    print(f"\n完成:成功 {len(ok)} / 失败 {len(fail)} / 共 {len(URLS)}")
    print(f"总耗时 {elapsed:.2f}s(单请求平均 {avg:.2f}s)")
    print(f"对比:若同步串行,大约要 {avg * len(URLS):.1f}s —— 这就是异步省下的时间")


if __name__ == "__main__":
    # ★ 忘了 asyncio.run() 启动,协程根本不会执行,程序会"什么都不做"
    asyncio.run(main())
