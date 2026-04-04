from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent

VERSION_FILES = {
    "old": [f"res{year}.txt" for year in range(2020, 2026)],
    "v2": [f"res{year}_2" for year in range(2020, 2026)],
    "v3": [f"res{year}_3" for year in range(2020, 2026)],
    "v4": [f"res{year}_4" for year in range(2020, 2026)],
    "v5": [f"res{year}_5" for year in range(2020, 2026)],
}

PATTERNS = {
    "final": r"最终资金:\s*([0-9.]+)",
    "ret": r"总收益率:\s*([0-9.+-]+)%",
    "trades": r"交易次数:\s*(\d+)",
    "win": r"胜率:\s*([0-9.+-]+)%",
    "sharpe": r"夏普比率:\s*([0-9.+-]+)",
    "dd": r"最大回撤:\s*([0-9.+-]+)%",
}


def parse_file(name: str) -> dict:
    text = (ROOT / name).read_text(encoding="utf-16")
    return {
        "file": name,
        "final": float(re.search(PATTERNS["final"], text).group(1)),
        "ret": float(re.search(PATTERNS["ret"], text).group(1)),
        "trades": int(re.search(PATTERNS["trades"], text).group(1)),
        "win": float(re.search(PATTERNS["win"], text).group(1)),
        "sharpe": float(re.search(PATTERNS["sharpe"], text).group(1)),
        "dd": float(re.search(PATTERNS["dd"], text).group(1)),
    }


def score_rows(rows: list[dict]) -> dict:
    rets = [row["ret"] for row in rows]
    sharpes = [row["sharpe"] for row in rows]
    drawdowns = [row["dd"] for row in rows]
    min_ret, max_ret = min(rets), max(rets)
    min_sharpe, max_sharpe = min(sharpes), max(sharpes)
    min_dd, max_dd = min(drawdowns), max(drawdowns)

    scored = []
    for row in rows:
        ret_score = 100 if max_ret == min_ret else (row["ret"] - min_ret) / (max_ret - min_ret) * 100
        sharpe_score = 100 if max_sharpe == min_sharpe else (row["sharpe"] - min_sharpe) / (max_sharpe - min_sharpe) * 100
        dd_score = 100 if max_dd == min_dd else (max_dd - row["dd"]) / (max_dd - min_dd) * 100
        total_score = round((ret_score + sharpe_score + dd_score) / 3, 2)
        scored.append({**row, "score": total_score})

    avg = round(sum(row["score"] for row in scored) / len(scored), 2)
    avg_ret = round(sum(row["ret"] for row in rows) / len(rows), 2)
    avg_sharpe = round(sum(row["sharpe"] for row in rows) / len(rows), 2)
    avg_dd = round(sum(row["dd"] for row in rows) / len(rows), 2)
    return {"rows": scored, "avg": avg, "avg_ret": avg_ret, "avg_sharpe": avg_sharpe, "avg_dd": avg_dd}


def comparable_scores(grouped_rows: dict[str, list[dict]]) -> dict[str, float]:
    all_rows = [row for rows in grouped_rows.values() for row in rows]
    rets = [row["ret"] for row in all_rows]
    sharpes = [row["sharpe"] for row in all_rows]
    drawdowns = [row["dd"] for row in all_rows]
    min_ret, max_ret = min(rets), max(rets)
    min_sharpe, max_sharpe = min(sharpes), max(sharpes)
    min_dd, max_dd = min(drawdowns), max(drawdowns)

    result = {}
    for version, rows in grouped_rows.items():
        scores = []
        for row in rows:
            ret_score = (row["ret"] - min_ret) / (max_ret - min_ret) * 100
            sharpe_score = (row["sharpe"] - min_sharpe) / (max_sharpe - min_sharpe) * 100
            dd_score = (max_dd - row["dd"]) / (max_dd - min_dd) * 100
            scores.append((ret_score + sharpe_score + dd_score) / 3)
        result[version] = round(sum(scores) / len(scores), 2)
    return result


def main():
    grouped_rows = {version: [parse_file(name) for name in files] for version, files in VERSION_FILES.items()}
    within = {version: score_rows(rows) for version, rows in grouped_rows.items()}
    comparable = comparable_scores(grouped_rows)
    print(json.dumps({"within": within, "comparable": comparable}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
