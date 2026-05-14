# Strategy5 High Frequency — 高频策略技术文档

> **版本**: v1.0 | **对应脚本**: `test_strategy5_highfreq.py` | **策略类**: `Strategy5HighFrequency`
>
> 本文档描述当前项目中的高频主线策略实现。它基于 `Strategy5` 演进而来，目标是在 `BTC/BNB/SOL/ETH` 上把交易频率提升到约 `2-3 天/次`，同时尽量维持可接受的夏普率和回撤水平。

---

## 一、入口与文件

- 回测入口：`./venv/bin/python test_strategy5_highfreq.py`
- 主策略类：`trend/strategy5_medium.py` 中的 `Strategy5HighFrequency`
- 参数定义：`test_strategy5_highfreq.py`
- 普通版策略：`trend/strategy5.py` 中的 `Strategy5`

常用命令：

```bash
./venv/bin/python test_strategy5_highfreq.py
./venv/bin/python test_strategy5_highfreq.py BTC BNB
./venv/bin/python test_strategy5_highfreq.py ETH --log
```

---

## 二、策略定位

`Strategy5HighFrequency` 不是完全独立重写的新策略，而是在普通版 `Strategy5` 基础上，逐步引入更高频的趋势跟随机制后收敛出的正式版本。

核心目标：

- 比普通版更早识别趋势
- 比普通版更宽松地接受 1H 入场位置
- 比普通版更密集地在 15M 上触发入场
- 比普通版更快释放仓位，为下一次交易腾出空间
- 对 `BTC/BNB` 单独收紧，避免高频噪音失控

---

## 三、相对普通版的主要变化

### 1. 4H 趋势判定放宽

普通版要求：

- `price > EMA21 > EMA55` 才允许做多
- `price < EMA21 < EMA55` 才允许做空

高频版改为：

- 只要 `EMA21` 与 `EMA55` 方向成立
- 且价格站在两条均线中点同侧
- 即视为趋势有效

效果：

- 更早放行趋势
- 增加趋势初段与中段的可交易区间

### 2. 1H 入场位置更宽

普通版主要只认两类：

- `EMA21-EMA55` 带内标准回调
- `EMA21` 与 `EMA55` 的当根趋势交叉

高频版在此基础上增加：

- 浅回踩：价格不必完全回到均线带内，只要仍贴近 `EMA21`
- 最近交叉跟随：不必是“刚刚交叉的这一根”，交叉后几根内仍可跟随

效果：

- 减少错过趋势延续段
- 提高每年交易次数

### 3. 15M 触发从离散信号变成连续动量

普通版 15M 主要依赖：

- 结构突破
- RSI 上下穿 50
- RSI 偏置

高频版新增连续动量触发：

- 价格沿 `EMA21` 方向延续
- RSI 连续同向增强
- 价格离 `EMA21` 不过远

并在 `V3.1` 收敛后加入去噪条件：

- 最小价格推进
- 最小 RSI 变化
- EMA 斜率要求
- 连续同向收盘要求

效果：

- 这是高频版提升交易密度的核心来源

### 4. 退出更快

高频版参数相对普通版明显提速：

- `m15_breakout_lookback: 6 -> 3`
- `stop_loss_atr_multiplier: 1.5 -> 1.35`
- `min_holding_bars: 5 -> 2`
- `ema_exit_confirm_bars: 2 -> 1`
- `ema_exit_buffer_atr: 0.30 -> 0.08`

效果：

- 更快止损/止盈/EMA 出场
- 仓位释放更快
- 提高年化交易次数

---

## 四、核心参数差异

下表只列出最影响高频行为的参数。

| 参数 | 普通版 | 高频版 | 作用 |
| --- | ---: | ---: | --- |
| `m15_breakout_lookback` | `6` | `3` | 缩短突破观察窗口，提高触发密度 |
| `stop_loss_atr_multiplier` | `1.5` | `1.35` | 止损更近，提高仓位周转 |
| `min_holding_bars` | `5` | `2` | 更早允许退出 |
| `ema_exit_confirm_bars` | `2` | `1` | EMA 破位一根就确认 |
| `ema_exit_buffer_atr` | `0.30` | `0.08` | 更早触发 EMA 出场 |
| `crossover_atr_distance` | `0.5` | `0.75` | 交叉模式允许更宽入场距离 |
| `crossover_position_scale` | `0.9` | `1.0` | 交叉模式不再轻仓 |
| `crossover_adx_threshold` | `25` | `20` | 趋势启动门槛降低 |
| `h1_rsi_long_high` | `60` | `66` | 多头允许更强动量继续参与 |
| `h1_rsi_short_low` | `40` | `34` | 空头允许更弱 RSI 延续 |
| `m15_rsi_bias_long` | `52` | `50` | 多头更容易满足偏置 |
| `m15_rsi_bias_short` | `48` | `50` | 空头更容易满足偏置 |

高频版新增参数：

| 参数 | 默认值 | 作用 |
| --- | ---: | --- |
| `medium_shallow_atr_distance` | `0.48` | 1H 浅回踩距离 |
| `medium_recent_crossover_lookback` | `3` | 最近交叉允许回看根数 |
| `medium_recent_crossover_atr_distance` | `0.85` | 交叉跟随距 EMA21 的容忍度 |
| `medium_recent_crossover_adx_threshold` | `19` | 交叉跟随趋势强度门槛 |
| `medium_recent_crossover_spread_max_atr` | `1.35` | EMA 扩散度上限 |
| `medium_h4_trend_midpoint_ratio` | `0.25` | 4H 趋势中点放宽幅度 |
| `medium_continuation_rsi_long` | `50` | 15M 连续动量多头阈值 |
| `medium_continuation_rsi_short` | `50` | 15M 连续动量空头阈值 |
| `medium_continuation_ema_distance_atr` | `1.10` | 连续动量距 EMA21 容忍度 |
| `medium_continuation_min_price_move_atr` | `0.0` | 连续动量最小价格推进 |
| `medium_continuation_min_rsi_step` | `0.0` | 连续动量最小 RSI 变化 |
| `medium_continuation_require_ema_slope` | `False` | 是否要求 EMA 同向倾斜 |
| `medium_continuation_price_streak_bars` | `1` | 连续同向收盘根数 |

---

## 五、币种级自动参数覆盖

高频版不是所有币一套参数。当前正式入口会自动对不同币种覆盖参数。

### BTC

特点：

- 明显收紧
- 目标是减少高频噪音

主要调整：

- 更小的浅回踩区
- 更短的交叉回看
- 更高的 ADX 要求
- 更严格的 15M 连续动量要求

### BNB

特点：

- 收紧程度略低于 BTC
- 目标是保留频率，同时抑制低质量连追

### ETH

特点：

- 基本保留高频节奏
- 只做轻微趋势确认调整

### SOL

特点：

- 保留最积极的高频参数
- 因为历史回测中 `SOL` 对高频逻辑适配最好

---

## 六、调参建议

### 如果想继续提高交易次数

优先调这些参数：

- `m15_breakout_lookback`
- `medium_shallow_atr_distance`
- `medium_recent_crossover_lookback`
- `medium_continuation_ema_distance_atr`

### 如果想优先提升夏普

优先调这些参数：

- `medium_recent_crossover_adx_threshold`
- `medium_continuation_min_price_move_atr`
- `medium_continuation_min_rsi_step`
- `ema_exit_buffer_atr`

### 如果想重点修 BTC/BNB

优先调这些参数：

- `medium_h4_trend_midpoint_ratio`
- `medium_continuation_require_ema_slope`
- `medium_continuation_price_streak_bars`
- `medium_recent_crossover_spread_max_atr`

---

## 七、与普通版的使用分工

当前项目建议这样理解两套正式入口：

- `test_strategy5.py`：普通版，偏稳健，交易更少
- `test_strategy5_highfreq.py`：高频版，偏趋势跟随密集入场，交易更多

如果你的目标是：

- 更稳的回撤和更高的一致性，优先用普通版
- `2-3 天一笔` 左右的交易节奏，优先用高频版

---

## 八、当前文档边界

本文档描述的是当前项目中的“正式高频版本”，即：

- 策略类：`Strategy5HighFrequency`
- 回测入口：`test_strategy5_highfreq.py`

历史中频实验脚本已经退出正式流程，不再作为推荐入口，也不再作为本文档维护对象。