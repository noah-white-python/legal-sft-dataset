"""Day 1 练习:读一个 CSV,打印行数、每列缺失值数量、去重后剩多少行。

用法:
    python exercises/inspect_csv.py 路径/到/文件.csv
    python exercises/inspect_csv.py data/raw/seed_disc_law.csv

这是 Day 1 "成果线" 要求的最小脚本,用到的 pandas 操作:
read_csv / shape / isna().sum() / drop_duplicates。
"""

import sys
import glob

# Windows 控制台默认 GBK,强制 UTF-8 输出,避免中文标签乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import pandas as pd


def inspect(path: str) -> None:
    df = pd.read_csv(path)

    print(f"\n===== {path} =====")
    print(f"行数:           {df.shape[0]}")
    print(f"列数:           {df.shape[1]}")
    print(f"列名:           {list(df.columns)}")

    print("\n每列缺失值数量:")
    # isna().sum() 逐列统计有多少个空值,是检查数据质量的第一步
    print(df.isna().sum().to_string())

    n_before = len(df)
    n_after = len(df.drop_duplicates())
    print(f"\n去重前: {n_before} 行")
    print(f"去重后: {n_after} 行  (重复 {n_before - n_after} 行)")


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python exercises/inspect_csv.py <csv文件或通配符>")
        sys.exit(1)

    # 支持传通配符,比如 data/raw/seed_*.csv
    paths: list[str] = []
    for arg in sys.argv[1:]:
        matched = glob.glob(arg)
        paths.extend(matched if matched else [arg])

    if not paths:
        print("没有匹配到任何文件")
        sys.exit(1)

    for p in paths:
        try:
            inspect(p)
        except Exception as e:
            # Day 1 教学点:一个文件出错不该让整个脚本崩,记下来继续
            print(f"[跳过] 读取 {p} 失败: {e}")


if __name__ == "__main__":
    main()
