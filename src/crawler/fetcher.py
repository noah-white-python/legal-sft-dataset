"""请求层 —— 带超时、重试、礼貌限速的同步 HTTP 封装。

爬虫一定会遇到偶发失败(超时、对方抖动、限频),所以"请求"这件事本身要够皮实:
失败了自动重试几次,每次间隔越等越久(指数退避),还失败才认输交给上层写死信。
"""

import time

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


class Fetcher:
    def __init__(self, max_retries: int = 3, timeout: int = 10, delay: float = 1.0):
        self.max_retries = max_retries   # 最多重试几次
        self.timeout = timeout           # 单次超时秒数
        self.delay = delay               # 每次请求后礼貌睡多久(限速、护 IP)
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get(self, url: str) -> str:
        """请求并返回 HTML。重试到底仍失败,则抛出最后一次异常,由上层写死信。"""
        last_err = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                # 显式按响应声明的编码解码,能挡掉一大半中文乱码问题
                resp.encoding = resp.apparent_encoding or resp.encoding
                time.sleep(self.delay)   # 成功也限速
                return resp.text
            except Exception as e:
                last_err = e
                # 指数退避:第 1 次等 1s,第 2 次 2s,第 3 次 4s,给对方喘息也避开瞬时抖动
                backoff = self.delay * (2 ** (attempt - 1))
                print(f"    重试 {attempt}/{self.max_retries}({url}):{e};{backoff:.0f}s 后再试")
                time.sleep(backoff)
        raise last_err  # 重试用尽,把最后的错误抛给上层
