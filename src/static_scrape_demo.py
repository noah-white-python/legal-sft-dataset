"""Day 3 成果线:静态页爬取(requests + BeautifulSoup),先不用异步,for 循环 + sleep。

对应计划:挑一个结构简单的静态网页,把标题列表抓下来,存成 CSV。
重点是"跑通"——能稳定抓到东西,比抓得快重要一百倍。

运行:
    python src/static_scrape_demo.py

目标站 books.toscrape.com:抓每本书的 标题/价格/库存,存成 CSV。
"""

import sys
import csv
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests
from bs4 import BeautifulSoup

BASE = "https://books.toscrape.com/catalogue/page-{}.html"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "demo_books.csv"

# 伪装成浏览器:很多站点会拒绝没有 User-Agent 的请求
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}


def parse_page(html: str) -> list[dict]:
    """从一页 HTML 里提取所有书的信息。解析逻辑集中在这里,换站点只改这个函数。"""
    soup = BeautifulSoup(html, "html.parser")
    books = []
    # CSS 选择器:每本书是一个 article.product_pod
    for pod in soup.select("article.product_pod"):
        title = pod.h3.a["title"]                      # 标题在 a 标签的 title 属性
        price = pod.select_one("p.price_color").text   # 价格
        stock = pod.select_one("p.instock.availability").text.strip()  # 库存
        books.append({"title": title, "price": price, "stock": stock})
    return books


def main():
    # session 复用底层连接,比每次新建快;设置统一 headers
    session = requests.Session()
    session.headers.update(HEADERS)

    all_books: list[dict] = []
    max_pages = 5  # 先只抓 5 页跑通;想要全部改成 50

    for page in range(1, max_pages + 1):
        url = BASE.format(page)
        try:
            resp = session.get(url, timeout=10)
            resp.raise_for_status()           # 4xx/5xx 直接抛异常
            books = parse_page(resp.text)
            all_books.extend(books)
            print(f"第 {page} 页:抓到 {len(books)} 本(累计 {len(all_books)})")
        except Exception as e:
            # 一页失败不该让整个程序崩,记下来跳过
            print(f"  [跳过] 第 {page} 页失败:{e}")
            continue

        time.sleep(1)  # ★ 礼貌性限速:别把对方站点打挂,也保护自己 IP

    # 存成 CSV(utf-8-sig 让 Excel 打开不乱码)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "price", "stock"])
        writer.writeheader()
        writer.writerows(all_books)

    print(f"\n共抓 {len(all_books)} 本,已存 -> {OUT}")


if __name__ == "__main__":
    main()
