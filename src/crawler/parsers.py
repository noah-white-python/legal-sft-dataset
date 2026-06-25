"""解析适配层 —— 整个爬虫里唯一和"具体站点长什么样"绑定的地方。

设计意图:storage / fetcher / run_crawler 都是通用的、跟站点无关的工程骨架。
要换爬另一个站,你只需在这里加一个 SiteParser:告诉它
  - list_pages(): 要爬哪些页面 URL
  - parse(html, url): 从一页 HTML 里抽出 [{question, answer}, ...]
其余断点续爬、去重、重试、死信、进度全自动复用。

下面 QuotesParser 是能直接跑通的演示;BaiduZhidaoParser 是给你 Day 5 填的模板。
"""

from bs4 import BeautifulSoup


class QuotesParser:
    """演示站 quotes.toscrape.com:专门给人练爬虫的合规沙盒,语录+作者,天然成对。

    这里把 语录文本 当作 question、作者+标签 当作 answer —— 纯粹为了演示
    "问答对"的存储流程。真实项目里换成 BaiduZhidaoParser 即可。
    """

    SOURCE = "quotes_demo"

    def list_pages(self) -> list[str]:
        # 这个站共 10 页
        return [f"https://quotes.toscrape.com/page/{i}/" for i in range(1, 11)]

    def parse(self, html: str, url: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        out = []
        for q in soup.select("div.quote"):
            text = q.select_one("span.text").get_text(strip=True)
            author = q.select_one("small.author").get_text(strip=True)
            tags = [t.get_text(strip=True) for t in q.select("a.tag")]
            out.append({
                "question": text,
                "answer": f"—— {author}(标签:{', '.join(tags) or '无'})",
            })
        return out


class BaiduZhidaoParser:
    """【Day 5 填空模板】百度知道「法律」分类问答。

    步骤提示(动手时按这个来):
      1. 先在浏览器打开一个法律问答页,右键"查看网页源代码",搜你要的"问题/答案"
         文字。搜得到 → requests+BeautifulSoup 就够;搜不到 → 内容是 JS 动态加载的,
         去 F12 Network 找返回 JSON 的接口直接请求(优先),实在不行才上 Playwright。
      2. 用浏览器"检查元素"找到 问题标题 和 最佳回答 对应的 CSS 选择器,填到下面。
      3. list_pages 里换成真实的分类列表页/详情页 URL 生成逻辑。
      4. 先用 run_crawler.py 跑 500 条试错(计划 Day 5),把坑踩出来再上量。

    合规与礼貌:遵守对方 robots.txt,降速(加大 fetcher 的 delay),法律数据注意脱敏。
    """

    SOURCE = "baidu_zhidao"

    def list_pages(self) -> list[str]:
        # TODO(Day5): 替换成真实的待爬 URL 列表
        raise NotImplementedError("Day 5 在这里填:生成百度知道法律问答的页面 URL 列表")

    def parse(self, html: str, url: str) -> list[dict]:
        # TODO(Day5): 用真实选择器替换下面两行
        soup = BeautifulSoup(html, "html.parser")
        question = ""   # 例:soup.select_one("选择器").get_text(strip=True)
        answer = ""     # 例:soup.select_one("选择器").get_text(strip=True)
        if not question or not answer:
            return []
        return [{"question": question, "answer": answer}]


# 站点注册表:run_crawler.py 用 --site 名字来选用哪个解析器
SITES = {
    "quotes": QuotesParser,
    "baidu": BaiduZhidaoParser,
}
