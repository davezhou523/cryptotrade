"""
下载 Binance 多币种多周期 K线数据
- 币种: BTCUSDT, BNBUSDT, SOLUSDT, XRPUSDT
- 周期: 5m, 15m, 1h, 4h
- 时间范围: 2019年 ~ 2026年（当前时间）
- 每个周期单独一个 CSV 文件，存储于 data/{SYMBOL}/binance/ 目录下
"""
import sys
import os
from datetime import datetime, timezone

# 将项目根目录加入 sys.path，以便导入 data 包
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.binance import BinanceDataFetcher


# ======================== 可配置参数 ========================

# 交易对列表（Binance 格式，如 BTCUSDT）
SYMBOLS = ["BTCUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]

# K线周期
INTERVALS = ["5m", "15m", "1h", "4h"]

# 数据起始年份（含）
START_YEAR = 2019

# 数据结束年份（含），自动取当前年份
END_YEAR = datetime.now(timezone.utc).year

# 市场类型: "spot" 现货 / "futures" 永续合约
MARKET_TYPE = "futures"

# 保存根目录（相对于 data/ 目录）
SAVE_ROOT = os.path.dirname(__file__)

# ==========================================================


def downloadSingleSymbol(fetcher, symbol, interval, startYear, endYear, saveDir):
    """
    下载单个币种、单个周期的全部年份数据
    :param fetcher: BinanceDataFetcher 实例
    :param symbol: 交易对，如 "BTCUSDT"
    :param interval: K线周期，如 "5m"
    :param startYear: 起始年份（含）
    :param endYear: 结束年份（含）
    :param saveDir: CSV 保存目录
    :return: 成功下载的年份数量
    """
    nowUtc = datetime.now(timezone.utc)
    successCount = 0

    for year in range(startYear, endYear + 1):
        # 计算该年的起止时间
        yearStart = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        yearEnd = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        # 如果年份的起始时间已经超过当前时间，跳过
        yearEnd = min(yearEnd, nowUtc)
        if yearStart >= nowUtc:
            print(f"  [{symbol} {interval}] {year} 年在未来区间，已跳过。")
            continue

        print(f"  [{symbol} {interval}] 正在下载 {year} 年数据...")

        csvFile = fetcher.fetch_klines(
            symbol=symbol,
            interval=interval,
            start_time=yearStart,
            end_time=yearEnd,
            save_dir=saveDir
        )

        if csvFile:
            print(f"  [{symbol} {interval}] {year} 年数据完成 → {csvFile}")
            successCount += 1
        else:
            print(f"  [{symbol} {interval}] {year} 年数据下载失败！")

    return successCount


def main():
    """
    主函数：循环遍历所有币种和周期，逐个下载 K线数据
    """
    print("=" * 60)
    print("Binance 多币种多周期 K线数据下载工具")
    print(f"币种: {', '.join(SYMBOLS)}")
    print(f"周期: {', '.join(INTERVALS)}")
    print(f"年份范围: {START_YEAR} ~ {END_YEAR}")
    print(f"市场类型: {MARKET_TYPE}")
    print("=" * 60)

    # 创建数据获取器（永续合约）
    fetcher = BinanceDataFetcher(market_type=MARKET_TYPE)

    totalTasks = len(SYMBOLS) * len(INTERVALS)
    completedTasks = 0
    failedTasks = 0

    for symbol in SYMBOLS:
        # 从交易对中提取币种简称，如 "BTCUSDT" → "BTC"
        coinName = symbol.replace("USDT", "")

        # 每个币种一个子目录：data/{COIN}/binance
        saveDir = os.path.join(SAVE_ROOT, coinName, "binance")

        print(f"\n{'=' * 50}")
        print(f"开始下载 {symbol} 数据 → {saveDir}")
        print(f"{'=' * 50}")

        for interval in INTERVALS:
            successCount = downloadSingleSymbol(
                fetcher=fetcher,
                symbol=symbol,
                interval=interval,
                startYear=START_YEAR,
                endYear=END_YEAR,
                saveDir=saveDir
            )

            # 至少有一年数据下载成功则视为该周期任务完成
            if successCount > 0:
                completedTasks += 1
            else:
                failedTasks += 1

    # 打印汇总
    print("\n" + "=" * 60)
    print(f"全部下载任务完成！")
    print(f"总任务数: {totalTasks}  成功: {completedTasks}  失败: {failedTasks}")
    print("=" * 60)


if __name__ == "__main__":
    main()
