"""自建爬虫工程(Day 5-6)。

模块划分:
- storage.py   sqlite 存储:去重、断点续爬、死信表
- fetcher.py   带超时/重试的同步请求封装
- parsers.py   站点解析适配层(换站点只改这里)
- run_crawler.py  主程序:把上面三块串起来 + tqdm 进度监控
"""
