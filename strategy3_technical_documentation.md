# Strategy3 技术文档

## 一、策略概述

Strategy3 是一个基于多时间周期分析的趋势跟踪策略，核心思想是 **"4H判断趋势方向 → 1H等待回调到位 → 15M确认入场信号"**，在趋势中通过回调寻找高盈亏比入场点。

### 交易框架

```
① 4H 判断趋势方向
   ├── 价格 > EMA21 > EMA55 → 只做多
   ├── 价格 < EMA21 < EMA55 → 只做空
   └── EMA缠绕/交叉 → 震荡，不交易

② 1H 判断回调位置（是否回调到位）
   ├── 多头：价格回踩到 EMA21/EMA55 区间 → 进入观察区
   ├── 空头：价格反弹到 EMA21/EMA55 区间 → 进入观察区
   └── 未到均线区间 → 等待

③ 15M 判断入场信号（触发交易）
   ├── 做多：RSI上破50 + 突破小结构高点 → BUY
   ├── 做空：RSI下破50 + 跌破小结构低点 → SELL
   └── 无信号 → 继续等待

④ 风控执行
   ├── 止损 = ATR × 止损倍数（15M）
   ├── 单笔风险 ≤ 配置比例
   └── 仓位自动计算

⑤ 持仓管理
   ├── +1R → 止损移到成本（保本）
   ├── +3R → 止盈一半
   └── EMA21破位 → 全部平仓

⑥ 退出 → 回到等待状态
```

### 核心理念

> 价格 > EMA21 > EMA55 ≠ 买点。真正的买点在于：**回调到位 + 小周期确认**。

---

## 二、多时间周期架构

| 周期 | 数据源索引 | 主要功能 | 核心指标 | 最小数据量 |
|------|-----------|---------|----------|-----------|
| 4H | `datas[0]` | 趋势方向判断 | EMA21, EMA55 | 55根（EMA55预热） |
| 1H | `datas[1]` | 回调位置确认 | EMA21, EMA55, RSI(14) | 60根（EMA55+5缓冲） |
| 15M | `datas[2]` | 入场信号/止损/出场 | EMA21, ATR(14), RSI(14) | 8根（lookback+2） |

---

## 三、EMA结构 → 操作决策总表

### 做多结构判断（1小时）

| EMA结构 | 价格位置 | 含义 | 操作 |
|---------|---------|------|------|
| 价格 > EMA21 > EMA55 | 强趋势上方 | 上涨加速中 | ❌ 不追（等回调） |
| EMA21 > 价格 > EMA55 | 回调区间 | 健康回调 | ✅ 准备做多 |
| 价格 ≈ EMA55 | 深回调 | 风险区 | ⚠️ 轻仓（缩放0.9） |
| 价格 < EMA55 | 结构破坏 | 可能反转 | ❌ 不做多 |

### 做空结构判断（1小时）

| EMA结构 | 价格位置 | 含义 | 操作 |
|---------|---------|------|------|
| 价格 < EMA21 < EMA55 | 强趋势下方 | 下跌加速中 | ❌ 不追空 |
| EMA21 < 价格 < EMA55 | 反弹区间 | 健康回调 | ✅ 准备做空 |
| 价格 ≈ EMA55 | 深反弹 | 风险区 | ⚠️ 轻仓（缩放0.9） |
| 价格 > EMA55 | 结构破坏 | 可能反转 | ❌ 不做空 |

### 回调 vs 反转判断

| 类型 | 1H EMA关系 | 结构 | RSI | EMA21方向 | 结论 |
|------|-----------|------|-----|----------|------|
| 多头回调 | EMA21 > EMA55 | 未破前低 | ≈50 | 上升 | ✅ 做多 |
| 多头反转 | EMA21走平/下拐 | 破前低 | <40 | 走平/下拐 | ❌ 停止做多 |
| 空头回调 | EMA21 < EMA55 | 未破前高 | ≈60 | 下降 | ✅ 做空 |
| 空头反转 | EMA21上拐 | 破前高 | >60 | 上拐 | ❌ 停止做空 |

---

## 四、参数配置

### 4.1 指标周期参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `h4_ema_fast` | 21 | 4H快速EMA周期（短期趋势） |
| `h4_ema_slow` | 55 | 4H慢速EMA周期（长期趋势） |
| `h1_ema_fast` | 21 | 1H快速EMA周期 |
| `h1_ema_slow` | 55 | 1H慢速EMA周期 |
| `h1_rsi_period` | 14 | 1H RSI周期 |
| `m15_ema_period` | 21 | 15M EMA周期（出场判断） |
| `m15_atr_period` | 14 | 15M ATR周期（波动率/止损/仓位） |
| `m15_rsi_period` | 14 | 15M RSI周期（入场信号） |

### 4.2 风控与仓位参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `risk_per_trade` | 0.03 | 单笔风险比例（3%），硬上限3% |
| `max_position_size` | 0.55 | 最大仓位占总资金比例（55%） |
| `deep_pullback_scale` | 0.9 | 深回调仓位缩放系数（90%仓位） |
| `pullback_deep_band` | 0.003 | 深回调判定带（距EMA55≤0.3%） |
| `stop_loss_atr_multiplier` | 1.5 | 止损距离 = ATR × 此倍数 |
| `min_holding_bars` | 5 | 最小持仓K线数（防噪音洗出） |
| `ema_exit_confirm_bars` | 2 | EMA破位需连续确认K线数 |
| `ema_exit_buffer_atr` | 0.30 | EMA破位缓冲带 = ATR × 此倍数 |

### 4.3 杠杆与约束参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `leverage` | 7.0 | 杠杆倍数 |
| `max_leverage_ratio` | 0.92 | 最大杠杆使用率（92%） |
| `max_positions` | 1 | 最大同时持仓数 |
| `max_consecutive_losses` | 3 | 连续亏损暂停阈值 |
| `max_daily_loss_pct` | 0.07 | 最大日亏损比例（7%） |
| `max_drawdown_pct` | 0.15 | 触发回撤缩放的回撤比例（15%） |
| `drawdown_position_scale` | 0.5 | 回撤缩放系数（仓位打5折） |

### 4.4 信号过滤参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `require_both_entry_signals` | False | 入场信号组合模式（True=AND, False=OR） |
| `h1_rsi_long_low` | 42 | 1H多头RSI下限 |
| `h1_rsi_long_high` | 60 | 1H多头RSI上限 |
| `h1_rsi_short_low` | 40 | 1H空头RSI下限 |
| `h1_rsi_short_high` | 58 | 1H空头RSI上限 |
| `m15_breakout_lookback` | 6 | 15M突破结构回顾期（K线数） |
| `m15_rsi_bias_long` | 52 | 15M多头RSI偏置阈值 |
| `m15_rsi_bias_short` | 48 | 15M空头RSI偏置阈值 |

### 4.5 币种级参数覆盖

不同币种波动特性不同，可在测试脚本中通过 `SYMBOL_PARAMS_OVERRIDE` 进行覆盖：

```python
SYMBOL_PARAMS_OVERRIDE = {
    "XRP": dict(
        risk_per_trade=0.02,               # 3%→2%
        stop_loss_atr_multiplier=2.0,      # 1.5→2.0，适应高波动
        ema_exit_buffer_atr=0.4,           # 0.30→0.40
        leverage=5.0,                      # 7→5
    ),
}
```

---

## 五、核心判断逻辑详解

### 5.1 4H趋势方向判断（`get_trend_direction`）

```
输入: 4H收盘价, EMA21, EMA55
输出: 'bullish' | 'bearish' | 'sideways' | None

判断逻辑:
  if 数据不足 (< h4_ema_slow根):  return None
  if 价格 > EMA21 > EMA55:        return 'bullish'   (多头排列)
  if 价格 < EMA21 < EMA55:        return 'bearish'   (空头排列)
  其他:                            return 'sideways'  (震荡，不交易)
```

### 5.2 1H回调条件判断（`check_pullback_condition`）

```
输入: trend_direction
输出: True/False（是否满足回调入场条件）
副作用: 设置 pullback_scale（回调仓位缩放系数）

多头回调判断流程:
  1. 数据充足? (≥ h1_ema_slow + 5根)           → 否: False
  2. 价格 > EMA带上界?                          → 是: 不追涨, False
  3. 价格 < EMA带下界?                          → 是: 结构破坏, False
  4. 价格在EMA带内?                             → 否: False
  5. 价格 < 前低点?                              → 是: 反转, False
  6. EMA21走平/下拐? (当前≤前值)                 → 是: 反转, False
  7. RSI ∈ [h1_rsi_long_low, h1_rsi_long_high]? → 否: False
  8. |价格-EMA55|/EMA55 ≤ pullback_deep_band?   → 是: 深回调, pullback_scale=0.9
  → 通过所有检查: True

空头回调判断流程: (镜像逻辑)
  1. 数据充足?
  2. 价格 < EMA带下界?                          → 不追空
  3. 价格 > EMA带上界?                          → 结构破坏
  4. 价格在EMA带内?
  5. 价格 > 前高点?                              → 反转
  6. EMA21走平/上拐? (当前≥前值)                 → 反转
  7. RSI ∈ [h1_rsi_short_low, h1_rsi_short_high]?
  8. 深回调检测
```

### 5.3 15M入场信号判断（`check_entry_signal`）

```
输入: trend_direction
输出: True/False

多头入场条件:
  结构突破: 收盘价 > 近6根K线最高点
  RSI信号:  RSI > 50 且 前值 ≤ 50（上穿50中线）
  RSI偏置:  RSI ≥ 52

空头入场条件:
  结构突破: 收盘价 < 近6根K线最低点
  RSI信号:  RSI < 50 且 前值 ≥ 50（下穿50中线）
  RSI偏置:  RSI ≤ 48

信号组合模式:
  OR模式  (require_both_entry_signals=False): RSI信号 OR 结构突破 → 入场
  AND模式 (require_both_entry_signals=True):  结构突破 AND (RSI信号 OR 偏置) → 入场
```

---

## 六、仓位计算逻辑（`calculate_position_size`）

### 计算公式

```
1. 止损距离 = ATR × stop_loss_atr_multiplier
2. 风险比例 = min(risk_per_trade, 0.03)        ← 硬上限3%
3. 风险金额 = 权益 × 风险比例
4. 风险仓位 = 风险金额 ÷ 止损距离
5. 现金上限 = (权益 × max_position_size) ÷ 价格
6. 杠杆上限 = (权益 × leverage × max_leverage_ratio) ÷ 价格
7. 基础仓位 = min(风险仓位, 现金上限, 杠杆上限)
8. 最终仓位 = 基础仓位 × 回撤缩放 × 回调缩放
```

### 缩放系数

| 缩放类型 | 触发条件 | 缩放值 | 说明 |
|---------|---------|--------|------|
| 回撤缩放 | 回撤 ≥ max_drawdown_pct(15%) | drawdown_position_scale(0.5) | 回撤过大，仓位减半 |
| 回调缩放 | 价格距EMA55 ≤ pullback_deep_band(0.3%) | deep_pullback_scale(0.9) | 深回调轻仓 |

---

## 七、止损止盈设置（`set_stop_loss_take_profit`）

### 计算公式

```
R = ATR × stop_loss_atr_multiplier（止损距离/风险单位）

多头:
  止损   = 入场价 - R
  止盈1  = 入场价 + R    （+1R，触发后止损移到成本）
  止盈2  = 入场价 + 3R   （+3R，触发后平仓一半）

空头:
  止损   = 入场价 + R
  止盈1  = 入场价 - R    （-1R，触发后止损移到成本）
  止盈2  = 入场价 - 3R   （-3R，触发后平仓一半）
```

### 持仓管理流程

```
入场 → 止损/止盈1/止盈2 已设置
  │
  ├─ 触及止损 → 全部平仓
  │
  ├─ 触及止盈1 (+1R) → 止损移到入场价（保本），继续持有
  │
  ├─ 触及止盈2 (+3R) → 平仓一半，剩余仓位等EMA破位出场
  │
  └─ EMA破位 → 全部平仓（见第八节）
```

---

## 八、出场条件判断（`check_exit_conditions`）

### 8.1 止损出场

```
多头: 价格 ≤ 止损价 → 全平
空头: 价格 ≥ 止损价 → 全平
```

### 8.2 移动止损到成本

```
触发条件: 价格达到止盈1 (+1R) 且 止损未移动过
操作:     止损价 = 入场价（保本）
```

### 8.3 部分止盈

```
触发条件: 价格达到止盈2 (+3R) 且 未执行过部分止盈
操作:     平仓一半
```

### 8.4 EMA破位出场

```
缓冲带 = ATR × ema_exit_buffer_atr

多头破位条件:
  1. 持仓K线数 ≥ min_holding_bars(5)
  2. 价格 < EMA21 - 缓冲带
  3. 连续 ema_exit_confirm_bars(2) 根K线满足条件

空头破位条件:
  1. 持仓K线数 ≥ min_holding_bars(5)
  2. 价格 > EMA21 + 缓冲带
  3. 连续 ema_exit_confirm_bars(2) 根K线满足条件
```

---

## 九、风险管理机制（`risk_management_check`）

### 9.1 多层风控体系

```
风险检查流程（每根K线执行）:
  │
  ├─ 1. 连续亏损检查
  │     当日连续亏损 ≥ max_consecutive_losses(3) → 禁止开仓
  │
  ├─ 2. 日亏损检查
  │     当日亏损比例 ≥ max_daily_loss_pct(7%) → 禁止开仓
  │
  ├─ 3. 回撤缩放（update_drawdown_scale）
  │     当前回撤 ≥ max_drawdown_pct(15%) → 仓位缩放为50%
  │
  └─ 4. 持仓数量检查
        当前持仓数 ≥ max_positions(1) → 禁止开仓
```

### 9.2 日级别重置

```
每日开始时重置:
  - daily_start_value = 当日开盘时权益
  - daily_consecutive_losses = 0
```

---

## 十、策略主循环（`next`）

### 执行流程图

```
每根15M K线触发 next():
  │
  ├─ 1. 日期检查: 新的一天? → 重置日统计
  │
  ├─ 2. 更新价格结构: update_levels()
  │     更新15M最近高低点、1H最近高低点
  │
  ├─ 3. 订单检查: 有未完成订单? → 等待，return
  │
  ├─ 4. 持仓管理:
  │     ├─ 有持仓? → bars_since_entry += 1
  │     ├─ 检查出场: check_exit_conditions()
  │     │   ├─ 止损 → 全平
  │     │   ├─ 部分止盈 → 平半仓
  │     │   └─ EMA破位 → 全平
  │     └─ 有出场信号? → 执行出场，return
  │
  ├─ 5. 已有持仓? → return（单仓限制）
  │
  ├─ 6. 风险检查: risk_management_check()
  │     不通过 → return
  │
  ├─ 7. 趋势判断: get_trend_direction()
  │     None/sideways → return（震荡不交易）
  │
  ├─ 8. 回调条件: check_pullback_condition(trend)
  │     不满足 → return
  │
  ├─ 9. 入场信号: check_entry_signal(trend)
  │     无信号 → return
  │
  ├─ 10. 仓位计算: calculate_position_size()
  │     size ≤ 0 → return
  │
  └─ 11. 执行入场:
        ├─ 设置信号价、止损止盈
        ├─ 记录入场上下文日志
        └─ 发出买入/卖出订单
```

---

## 十一、状态变量一览

### 订单与仓位状态

| 变量 | 类型 | 说明 |
|------|------|------|
| `order` | Order/None | 当前活跃订单 |
| `current_position` | str/None | 持仓方向（'long'/'short'/None） |
| `entry_direction` | str/None | 入场方向 |
| `entry_price` | float/None | 入场价格 |
| `entry_time` | datetime/None | 入场时间 |
| `stop_loss` | float/None | 止损价格 |
| `take_profit` | list/None | 止盈价格 [1R, 3R] |
| `stop_moved_to_cost` | bool | 止损是否已移到成本 |
| `partial_take_profit_done` | bool | 是否已执行部分止盈 |
| `signal_price` | float/None | 信号触发时15M收盘价 |

### 价格结构跟踪

| 变量 | 类型 | 说明 |
|------|------|------|
| `m15_last_high` | float/None | 15M最近高点（突破判断） |
| `m15_last_low` | float/None | 15M最近低点（突破判断） |
| `h1_last_high` | float/None | 1H最近高点（回调判断） |
| `h1_last_low` | float/None | 1H最近低点（回调判断） |
| `pullback_scale` | float | 回调仓位缩放系数（默认1.0） |

### 风险管理变量

| 变量 | 类型 | 说明 |
|------|------|------|
| `trade_count` | int | 总交易次数 |
| `win_count` | int | 盈利交易次数 |
| `consecutive_losses` | int | 全局连续亏损次数 |
| `daily_consecutive_losses` | int | 当日连续亏损次数 |
| `current_day` | date | 当前交易日 |
| `daily_start_value` | float | 当日开始时资金 |
| `max_portfolio_value` | float | 投资组合历史最高价值 |
| `drawdown_position_scale` | float | 回撤仓位缩放系数（默认1.0） |
| `bars_since_entry` | int | 自入场以来K线数 |
| `ema_break_count` | int | EMA破位连续计数 |

---

## 十二、回测配置

### Cerebro引擎配置

```python
cerebro.broker.setcash(10000.0)               # 初始资金
cerebro.broker.set_shortcash(True)             # 允许做空
cerebro.broker.setcommission(
    commission=0.001,                           # 0.1%手续费
    margin=0.2,                                 # 20%保证金
    stocklike=False                             # 期货模式
)
cerebro.broker.set_slippage_perc(0.001)         # 0.1%滑点
cerebro.broker.set_coc(True)                    # 收盘价成交
```

### 数据文件路径

```
data/{COIN}/binance/{symbol}_4h_{year}0101_{year}1231.csv
data/{COIN}/binance/{symbol}_1h_{year}0101_{year}1231.csv
data/{COIN}/binance/{symbol}_15m_{year}0101_{year}1231.csv
```

### CSV格式

| 列名 | 类型 | 说明 |
|------|------|------|
| datetime | str | 时间，格式 YYYY-MM-DD HH:MM:SS |
| open | float | 开盘价 |
| high | float | 最高价 |
| low | float | 最低价 |
| close | float | 收盘价 |
| volume | float | 成交量 |

---

## 十三、回测结果示例

### XRP（优化后参数: 风险2%, 止损2.0ATR, 杠杆5x, 缓冲带0.4ATR）

| 年份 | 最终资金 | 收益率 | 交易数 | 胜率 | 夏普比率 | 最大回撤 |
|------|---------|--------|--------|------|---------|---------|
| 2020 | 9711.21 | -2.89% | 37 | 40.5% | -0.32 | 8.25% |
| 2021 | 12715.31 | 27.15% | 36 | 44.4% | 1.87 | 7.47% |
| 2022 | 10915.94 | 9.16% | 32 | 53.1% | 1.30 | 2.62% |
| 2023 | 9272.36 | -7.28% | 44 | 25.0% | -1.66 | 8.62% |
| 2024 | 10397.18 | 3.97% | 33 | 51.5% | 0.84 | 2.47% |
| 2025 | 11349.07 | 13.49% | 40 | 55.0% | 1.88 | 2.28% |

### SOL（默认参数）

| 年份 | 最终资金 | 收益率 | 交易数 | 胜率 | 夏普比率 | 最大回撤 |
|------|---------|--------|--------|------|---------|---------|
| 2020 | 11025.56 | 10.26% | 12 | 66.7% | 2.33 | 2.51% |
| 2021 | 13150.36 | 31.50% | 39 | 48.7% | 2.27 | 3.76% |
| 2022 | 13620.55 | 36.21% | 30 | 73.3% | 3.04 | 2.86% |
| 2023 | 10093.87 | 0.94% | 30 | 30.0% | 0.19 | 3.41% |
| 2024 | 10792.73 | 7.93% | 39 | 46.2% | 1.27 | 2.36% |
| 2025 | 12494.62 | 24.95% | 42 | 64.3% | 2.74 | 3.46% |
