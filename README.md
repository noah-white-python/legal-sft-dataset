# legal-sft-dataset

构建一个**中文法律领域的 SFT(监督微调)数据集**:从公开来源采集"法律问答"对,经过清洗、去重、质量过滤,最终格式化成可直接用于大模型微调的训练数据。

## 为什么做这个

大模型在通用语料上预训练后,要靠 SFT 才能学会"按指令、按领域回答"。中文法律是一个**高价值、高门槛**的垂直领域:问答结构天然成对(咨询→解答),但公开的高质量数据稀缺。本项目就是把散落的法律问答整理成一份干净、可训练的数据集。

## 技术路线

```
采集 (collect) → 清洗 (clean) → 去重 (dedup) → 质量过滤 (filter) → 格式化 (format)
```

- **采集**:① HuggingFace 现成中文法律数据集冷启动;② 自建爬虫补充(百度知道等问答源)
- **清洗**:去 HTML 残留、空白、广告噪声,统一编码
- **去重**:精确去重 + 近似去重(MinHash / SimHash)
- **质量过滤**:剔除过短、答非所问、无专业含量的样本
- **格式化**:转成 SFT 训练格式(如 `{"instruction":..., "input":..., "output":...}`)

## 目录结构

```
legal-sft-dataset/
├── data/
│   ├── raw/          # 原始采集数据(不进 git,见 .gitignore)
│   └── processed/    # 清洗后/格式化后的数据
├── docs/
│   └── data_sources.md   # 数据源调研记录
├── exercises/        # 学习练习脚本(Day 1 的 pandas 练习等)
├── scripts/          # 可独立运行的工具脚本(下载、爬取、处理)
├── src/              # 项目核心代码(爬虫、清洗管线等)
├── requirements.txt
└── README.md
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 冷启动:从 HuggingFace 下载第一批中文法律数据(走国内镜像)
python scripts/download_seed_data.py

# 3. 用 pandas 看一眼数据质量
python exercises/inspect_csv.py data/raw/seed_*.csv
```

## 本周(第 1 周)计划

采集为主,目标:用现成数据集冷启动 + 自建爬虫走量,拿到第一批 1-2 万条真实法律问答。
详见 Obsidian 笔记《第1周学习计划-详细教学版》。

## 进度

- [x] Day 1 — 项目脚手架 + pandas/工程基础
- [x] Day 2 — HuggingFace 现成数据集冷启动(项目"有数据")
- [ ] Day 3 — 异步 + 静态页爬取
- [ ] Day 4 — 数据源调研
- [ ] Day 5 — 第一版爬虫(同步)
- [ ] Day 6 — 修 bug + 上量
- [ ] Day 7 — 复盘 + 周报
