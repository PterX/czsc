# -*- coding: utf-8 -*-
"""
author: zengbin93
email: zeng_bin8888@163.com
create_dt: 2023/4/19 23:27
describe: 绩效表现统计
"""
import numpy as np
import pandas as pd
from deprecated import deprecated
from collections import Counter


def cal_break_even_point(seq) -> float:
    """计算单笔收益序列的盈亏平衡点

    :param seq: 单笔收益序列，数据样例：[0.01, 0.02, -0.01, 0.03, 0.02, -0.02, 0.01, -0.01, 0.02, 0.01]
    :return: 盈亏平衡点
    """
    if sum(seq) < 0:
        return 1.0
    seq = np.cumsum(sorted(seq))  # type: ignore
    return (np.sum(seq < 0) + 1) / len(seq)  # type: ignore


@deprecated(reason="用不上了，策略回测统一用 rs_czsc.WeightBacktest 替代，支持扣费")
def subtract_fee(df, fee=1):
    """依据单品种持仓信号扣除手续费

    函数执行逻辑：

    1. 首先，函数对输入的df进行检查，确保其包含所需的列：'dt'（日期时间）和'pos'（持仓）。同时，检查'pos'列的值是否符合要求，即只能是0、1或-1。
    2. 如果df中不包含'n1b'（名义收益率）列，函数会根据'price'列计算'n1b'列。
    3. 然后，函数为输入的DataFrame df添加一个新列'date'，该列包含交易日期（从'dt'列中提取）。
    4. 接下来，函数根据持仓（'pos'）和名义收益率（'n1b'）计算'edge_pre_fee'（手续费前收益）和'edge_post_fee'（手续费后收益）两列。
    5. 函数根据持仓信号计算开仓和平仓的位置。
        开仓位置（open_pos）是持仓信号发生变化的位置（即，当前持仓与前一个持仓不同），并且当前持仓不为0。
        平仓位置（exit_pos）是持仓信号发生变化的位置（即，当前持仓与前一个持仓不同），并且前一个持仓不为0。
    6. 根据手续费规则，开仓时在第一个持仓K线上扣除手续费，平仓时在最后一个持仓K线上扣除手续费。
       函数通过将'edge_post_fee'列的值在开仓和平仓位置上分别减去手续费（fee）来实现这一逻辑。
    7. 最后，函数返回修改后的DataFrame df。

    :param df: 包含dt、pos、price、n1b列的DataFrame
    :param fee: 手续费，单位：BP
    :return: 修改后的DataFrame
    """
    assert "dt" in df.columns, "dt 列必须存在"
    assert "pos" in df.columns, "pos 列必须存在"
    assert all(x in [0, 1, -1] for x in df["pos"].unique()), "pos 列的值必须是 0, 1, -1 中的一个"

    if "n1b" not in df.columns:
        assert "price" in df.columns, "当n1b列不存在时，price 列必须存在"
        df["n1b"] = (df["price"].shift(-1) / df["price"] - 1) * 10000

    df["date"] = df["dt"].dt.date
    df["edge_pre_fee"] = df["pos"] * df["n1b"]
    df["edge_post_fee"] = df["pos"] * df["n1b"]

    # 扣费规则, 开仓扣费在第一个持仓K线上，平仓扣费在最后一个持仓K线上
    open_pos = (df["pos"].shift() != df["pos"]) & (df["pos"] != 0)
    exit_pos = (df["pos"].shift(-1) != df["pos"]) & (df["pos"] != 0)
    df.loc[open_pos, "edge_post_fee"] = df.loc[open_pos, "edge_post_fee"] - fee
    df.loc[exit_pos, "edge_post_fee"] = df.loc[exit_pos, "edge_post_fee"] - fee
    return df


@deprecated(reason="请使用 rs_czsc.daily_performance 替代")
def daily_performance(daily_returns, **kwargs):
    """采用单利计算日收益数据的各项指标

    函数计算逻辑：

    1. 首先，将传入的日收益率数据转换为NumPy数组，并指定数据类型为float64。
    2. 然后，进行一系列判断：如果日收益率数据为空或标准差为零或全部为零，则返回字典，其中所有指标的值都为零。
    3. 如果日收益率数据满足要求，则进行具体的指标计算：

        - 年化收益率 = 日收益率列表的和 / 日收益率列表的长度 * 252
        - 夏普比率 = 日收益率的均值 / 日收益率的标准差 * 标准差的根号252
        - 最大回撤 = 累计日收益率的最高累积值 - 累计日收益率
        - 卡玛比率 = 年化收益率 / 最大回撤（如果最大回撤不为零，则除以最大回撤；否则为10）
        - 日胜率 = 大于零的日收益率的个数 / 日收益率的总个数
        - 年化波动率 = 日收益率的标准差 * 标准差的根号252
        - 下行波动率 = 日收益率中小于零的日收益率的标准差 * 标准差的根号252
        - 非零覆盖 = 非零的日收益率个数 / 日收益率的总个数
        - 回撤风险 = 最大回撤 / 年化波动率；一般认为 1 以下为低风险，1-2 为中风险，2 以上为高风险

    4. 将所有指标的值存储在字典中，其中键为指标名称，值为相应的计算结果。

    :param daily_returns: 日收益率数据，样例：
        [0.01, 0.02, -0.01, 0.03, 0.02, -0.02, 0.01, -0.01, 0.02, 0.01]
    :param kwargs: 其他参数
        - yearly_days: int, 252, 一年的交易日数
    :return: dict
    """
    daily_returns = np.array(daily_returns, dtype=np.float64)
    yearly_days = kwargs.get("yearly_days", 252)

    if len(daily_returns) == 0 or np.std(daily_returns) == 0 or all(x == 0 for x in daily_returns):
        return {
            "绝对收益": 0,
            "年化": 0,
            "夏普": 0,
            "最大回撤": 0,
            "卡玛": 0,
            "日胜率": 0,
            "日盈亏比": 0,
            "日赢面": 0,
            "年化波动率": 0,
            "下行波动率": 0,
            "非零覆盖": 0,
            "盈亏平衡点": 0,
            "新高间隔": 0,
            "新高占比": 0,
            "回撤风险": 0,
        }

    annual_returns = np.sum(daily_returns) / len(daily_returns) * yearly_days
    sharpe_ratio = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(yearly_days)
    cum_returns = np.cumsum(daily_returns)
    dd = np.maximum.accumulate(cum_returns) - cum_returns
    max_drawdown = np.max(dd)
    kama = annual_returns / max_drawdown if max_drawdown != 0 else 10
    win_pct = len(daily_returns[daily_returns >= 0]) / len(daily_returns)
    daily_mean_loss = np.mean(daily_returns[daily_returns < 0]) if len(daily_returns[daily_returns < 0]) > 0 else 0
    daily_ykb = np.mean(daily_returns[daily_returns >= 0]) / abs(daily_mean_loss) if daily_mean_loss != 0 else 5

    annual_volatility = np.std(daily_returns) * np.sqrt(yearly_days)
    none_zero_cover = len(daily_returns[daily_returns != 0]) / len(daily_returns)

    downside_volatility = np.std(daily_returns[daily_returns < 0]) * np.sqrt(yearly_days)

    # 计算最大新高间隔
    max_interval = Counter(np.maximum.accumulate(cum_returns).tolist()).most_common(1)[0][1]

    # 计算新高时间占比
    high_pct = len([i for i, x in enumerate(dd) if x == 0]) / len(dd)

    def __min_max(x, min_val, max_val, digits=4):
        if x < min_val:
            x1 = min_val
        elif x > max_val:
            x1 = max_val
        else:
            x1 = x
        return round(x1, digits)

    sta = {
        "绝对收益": round(np.sum(daily_returns), 4),
        "年化": round(annual_returns, 4),
        "夏普": __min_max(sharpe_ratio, -5, 10, 2),
        "最大回撤": round(max_drawdown, 4),
        "卡玛": __min_max(kama, -10, 20, 2),
        "日胜率": round(win_pct, 4),
        "日盈亏比": round(daily_ykb, 4),
        "日赢面": round(win_pct * daily_ykb - (1 - win_pct), 4),
        "年化波动率": round(annual_volatility, 4),
        "下行波动率": round(downside_volatility, 4),
        "非零覆盖": round(none_zero_cover, 4),
        "盈亏平衡点": round(cal_break_even_point(daily_returns), 4),
        "新高间隔": max_interval,
        "新高占比": round(high_pct, 4),
        "回撤风险": round(max_drawdown / annual_volatility, 4),
    }
    return sta


def rolling_daily_performance(df: pd.DataFrame, ret_col, window=252, min_periods=100, **kwargs):
    """计算滚动日收益的各项指标

    :param df: pd.DataFrame, 日收益数据，columns=['dt', ret_col] 或者 index 为 datetime64[ns]
    :param ret_col: str, 收益列名
    :param window: int, 滚动窗口, 自然天数
    :param min_periods: int, 最小样本数
    :param kwargs: 其他参数

        - yearly_days: int, 252, 一年的交易日数
    """
    from czsc.eda import cal_yearly_days
    from rs_czsc import daily_performance

    if not df.index.dtype == "datetime64[ns]":
        df["dt"] = pd.to_datetime(df["dt"])
        df.set_index("dt", inplace=True)
    assert df.index.dtype == "datetime64[ns]", "index必须是datetime64[ns]类型, 请先使用 pd.to_datetime 进行转换"

    yearly_days = kwargs.get("yearly_days", cal_yearly_days(df.index.tolist()))

    df = df[[ret_col]].copy().fillna(0)
    df.sort_index(inplace=True, ascending=True)
    dts = sorted(df.index.to_list())
    res = []
    for edt in dts[min_periods:]:
        sdt = edt - pd.Timedelta(days=window)
        dfg = df[(df.index >= sdt) & (df.index <= edt)].copy()
        s = daily_performance(dfg[ret_col].to_list(), yearly_days=yearly_days)
        s["sdt"] = sdt
        s["edt"] = edt
        res.append(s)

    dfr = pd.DataFrame(res)
    return dfr


def evaluate_pairs(pairs: pd.DataFrame, trade_dir: str = "多空") -> dict:
    """评估开平交易记录的表现

    :param pairs: 开平交易记录，数据样例如下：

        ==========  ==========  ===================  ===================  ==========  ==========  ===========  ============  ==========  ==========
        标的代码     交易方向     开仓时间              平仓时间              开仓价格    平仓价格     持仓K线数    事件序列        持仓天数     盈亏比例
        ==========  ==========  ===================  ===================  ==========  ==========  ===========  ============  ==========  ==========
        DLi9001     多头        2019-02-25 21:36:00  2019-02-25 21:51:00     1147.8      1150.72           16  开多 -> 平多           0       25.47
        DLi9001     多头        2021-09-15 14:06:00  2021-09-15 14:09:00     3155.88     3153.61            4  开多 -> 平多           0       -7.22
        DLi9001     多头        2019-08-29 21:01:00  2019-08-29 22:54:00     1445.86     1454.55          114  开多 -> 平多           0       60.09
        DLi9001     多头        2021-10-11 21:46:00  2021-10-11 22:11:00     3631.77     3622.66           26  开多 -> 平多           0      -25.08
        DLi9001     多头        2020-05-13 09:16:00  2020-05-13 09:26:00     1913.13     1917.64           11  开多 -> 平多           0       23.55
        ==========  ==========  ===================  ===================  ==========  ==========  ===========  ============  ==========  ==========

    :param trade_dir: 交易方向，可选值 ['多头', '空头', '多空']
    :return: 交易表现
    """
    from czsc.objects import cal_break_even_point

    assert trade_dir in [
        "多头",
        "空头",
        "多空",
    ], "trade_dir 参数错误，可选值 ['多头', '空头', '多空']"

    pairs = pairs.copy()

    p = {
        "交易方向": trade_dir,
        "交易次数": 0,
        "累计收益": 0,
        "单笔收益": 0,
        "盈利次数": 0,
        "累计盈利": 0,
        "单笔盈利": 0,
        "亏损次数": 0,
        "累计亏损": 0,
        "单笔亏损": 0,
        "交易胜率": 0,
        "累计盈亏比": 0,
        "单笔盈亏比": 0,
        "盈亏平衡点": 1,
        "持仓天数": 0,
        "持仓K线数": 0,
    }

    if len(pairs) == 0:
        return p

    if trade_dir in ["多头", "空头"]:
        pairs = pairs[pairs["交易方向"] == trade_dir]
        if len(pairs) == 0:
            return p

    pairs = pairs.to_dict(orient="records")
    p["交易次数"] = len(pairs)
    p["盈亏平衡点"] = round(cal_break_even_point([x["盈亏比例"] for x in pairs]), 4)
    p["累计收益"] = round(sum([x["盈亏比例"] for x in pairs]), 2)
    p["单笔收益"] = round(p["累计收益"] / p["交易次数"], 2)
    p["持仓天数"] = round(sum([x["持仓天数"] for x in pairs]) / len(pairs), 2)
    p["持仓K线数"] = round(sum([x["持仓K线数"] for x in pairs]) / len(pairs), 2)

    win_ = [x for x in pairs if x["盈亏比例"] >= 0]
    if len(win_) > 0:
        p["盈利次数"] = len(win_)
        p["累计盈利"] = sum([x["盈亏比例"] for x in win_])
        p["单笔盈利"] = round(p["累计盈利"] / p["盈利次数"], 4)
        p["交易胜率"] = round(p["盈利次数"] / p["交易次数"], 4)

    loss_ = [x for x in pairs if x["盈亏比例"] < 0]
    if len(loss_) > 0:
        p["亏损次数"] = len(loss_)
        p["累计亏损"] = sum([x["盈亏比例"] for x in loss_])
        p["单笔亏损"] = round(p["累计亏损"] / p["亏损次数"], 4)

        p["累计盈亏比"] = round(p["累计盈利"] / abs(p["累计亏损"]), 4)
        p["单笔盈亏比"] = round(p["单笔盈利"] / abs(p["单笔亏损"]), 4)

    return p


def holds_performance(df, **kwargs):
    """组合持仓权重表现

    :param df: pd.DataFrame, columns=['dt', 'symbol', 'weight', 'n1b']
        数据说明，dt: 交易时间，symbol: 标的代码，weight: 权重，n1b: 名义收益率
        必须是每个时间点都有数据，如果某个时间点没有数据，可以增加一行数据，权重为0
    :param kwargs:

        - fee: float, 单边费率，BP
        - digits: int, 保留小数位数

    :return: pd.DataFrame, columns=['date', 'change', 'edge_pre_fee', 'cost', 'edge_post_fee']
    """
    fee = kwargs.get("fee", 15)
    digits = kwargs.get("digits", 2)  # 保留小数位数

    df = df.copy()
    df["weight"] = df["weight"].round(digits)
    df = df.sort_values(["dt", "symbol"]).reset_index(drop=True)

    dft = pd.pivot_table(df, index="dt", columns="symbol", values="weight", aggfunc="sum").fillna(0)
    df_turns = dft.diff().abs().sum(axis=1).reset_index()
    df_turns.columns = ["date", "change"]
    sdt = df["dt"].min()
    df_turns.loc[(df_turns["date"] == sdt), "change"] = df[df["dt"] == sdt]["weight"].sum()

    df_edge = df.groupby("dt")[['weight', 'n1b']].apply(lambda x: (x["weight"] * x["n1b"]).sum()).reset_index()
    df_edge.columns = ["date", "edge_pre_fee"]
    dfr = pd.merge(df_turns, df_edge, on="date", how="left")
    dfr["cost"] = dfr["change"] * fee / 10000  # 换手成本
    dfr["edge_post_fee"] = dfr["edge_pre_fee"] - dfr["cost"]  # 净收益
    return dfr


def top_drawdowns(returns: pd.Series, top: int = 10) -> pd.DataFrame:
    """分析最大回撤，返回最大回撤的波峰、波谷、恢复日期、回撤天数、恢复天数

    :param returns: pd.Series, 日收益率序列，index为日期
    :param top: int, optional, 返回最大回撤的数量，默认10
    :return: pd.DataFrame
    """
    returns = returns.copy()
    df_cum = returns.cumsum()
    underwater = df_cum - df_cum.cummax()

    drawdowns = []
    for _ in range(top):
        valley = underwater.idxmin()  # end of the period
        peak = underwater[:valley][underwater[:valley] == 0].index[-1]
        try:
            recovery = underwater[valley:][underwater[valley:] == 0].index[0]
        except IndexError:
            recovery = np.nan  # drawdown not recovered

        # Slice out draw-down period
        if not pd.isnull(recovery):
            underwater.drop(underwater[peak:recovery].index[1:-1], inplace=True)
        else:
            # drawdown has not ended yet
            underwater = underwater.loc[:peak]

        drawdown = df_cum.loc[valley] - df_cum.loc[peak]

        drawdown_days = (valley - peak).days
        recovery_days = (recovery - valley).days if not pd.isnull(recovery) else np.nan
        new_high_days = drawdown_days + recovery_days if not pd.isnull(recovery) else np.nan

        drawdowns.append((peak, valley, recovery, drawdown, drawdown_days, recovery_days, new_high_days))
        if (len(returns) == 0) or (len(underwater) == 0) or (np.min(underwater) == 0):
            break

    df_drawdowns = pd.DataFrame(
        drawdowns, columns=["回撤开始", "回撤结束", "回撤修复", "净值回撤", "回撤天数", "恢复天数", "新高间隔"]
    )
    return df_drawdowns


def psi(df: pd.DataFrame, factor, segment, **kwargs):
    """PSI 群体稳定性指标，反映数据在不同分箱中的分布变化

    PSI = ∑(实际占比 - 基准占比) * ln(实际占比 / 基准占比)

    参考：https://zhuanlan.zhihu.com/p/79682292  风控模型—群体稳定性指标(PSI)深入理解应用

    :param df: 数据, 必须包含 dt 和 col 列
    :param factor: 分组因子
    :param segment: 样本分组
    :param kwargs:
    :return: pd.DataFrame
    """
    dfg = df.groupby([factor, segment], observed=False).size().unstack().fillna(0).apply(lambda x: x / x.sum(), axis=0)
    dfg["总体分布"] = df.groupby(factor).size().values / len(df)
    base_col = "总体分布"

    cols = [x for x in dfg.columns if x != base_col]
    for rate_col in cols:
        dfg[f"{rate_col}_PSI"] = np.where(
            (dfg[base_col] != 0) & (dfg[rate_col] != 0),
            (dfg[rate_col] - dfg[base_col]) * np.log((dfg[rate_col] / dfg[base_col])),
            dfg[rate_col] - dfg[base_col],
        )
    psi_cols = [x for x in dfg.columns if x.endswith("_PSI")]
    dfg["PSI"] = dfg[psi_cols].mean(axis=1)
    dfg.loc["总计"] = dfg.sum(axis=0)
    return dfg
