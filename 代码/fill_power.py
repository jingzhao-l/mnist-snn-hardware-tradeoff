#!/usr/bin/env python3
"""
fill_power.py — 根据 Cadence 实测功耗填充 SNN trade-off CSV
============================================================
使用已测得的单 IF 神经元功耗 P_if_single_uW 和单 MAC 单元功耗 P_mac_single_uW，
按照 CSV 里约定的公式，为 snn_tradeoff_*.csv 填充功耗列。

当前采用的 ANN 并行度假设：
  parallelism = 1
  即假设 ANN 使用单个 MAC 单元串行完成全部 MAC 运算。
  这是最保守的 ANN 功耗基线，便于突出 SNN 事件驱动的节能优势。
  如需改为面积/延迟等价模型，可修改脚本顶部的 PARALLELISM 常量。

公式：
  P_SNN_uW  = P_if_single_uW * (Avg_Spikes_L1 + Avg_Spikes_L2)
            = P_if_single_uW * N_neurons * T * firing_rate
  P_ANN_uW  = P_mac_single_uW * (MAC_ops / parallelism)
  power_saving_percent = (P_ANN_uW - P_SNN_uW) / P_ANN_uW * 100
"""

import csv
import os

# -----------------------------------------------------------
# 可配置常量
# -----------------------------------------------------------
# 2MHz 时钟下 Cadence 实测动态功耗（单位 µW）
P_IF_DYNAMIC_UW = 2.627
P_MAC_DYNAMIC_UW = 4.876

# 静态功耗（输入全 1、CLK=0、CLR=0，DC 分析测得，单位 µW）
P_IF_STATIC_UW = 0.0059508
P_MAC_STATIC_UW = 0.005827

# IF 事件折算因子（activity factor）
# ============================================================
# 你测到的 P_if_dynamic 是 IF 神经元在整个仿真窗口内的“平均功耗”。
# 如果仿真窗口里只有一部分时钟周期真正发生了脉冲事件，
# 那么“每次脉冲事件的等效功耗”需要乘以一个活动因子：
#
#   correction_factor = 仿真窗口内的总时钟周期数 / 实际脉冲事件数
#                     = (stop_time * f_clk) / N_spikes
#
# 实际测试参数（你刚确认）：
#   stop_time = 5.5us, f_clk = 2MHz -> 总时钟周期 = 5.5us * 2MHz = 11
#   SPIKE_IN=1 覆盖了 3 个 CLK 下降沿 -> 3 个脉冲事件
#   correction_factor = 11 / 3 ≈ 3.67
IF_EVENT_CORRECTION_FACTOR = 11.0 / 3.0

# 用于计算的有效功耗 = (总动态 - 静态漏电) × 事件折算因子
P_IF_SINGLE_UW = (P_IF_DYNAMIC_UW - P_IF_STATIC_UW) * IF_EVENT_CORRECTION_FACTOR
P_MAC_SINGLE_UW = P_MAC_DYNAMIC_UW - P_MAC_STATIC_UW

# 网络结构参数
INPUT_DIM = 784
HIDDEN_DIM = 300
OUTPUT_DIM = 10
N_NEURONS = HIDDEN_DIM + OUTPUT_DIM
MAC_OPS = INPUT_DIM * HIDDEN_DIM + HIDDEN_DIM * OUTPUT_DIM  # 238200

# 时钟频率（MHz），用于把 µW 换算成 pJ
F_CLK_MHZ = 2.0

# ANN 并行度：1 = 单 MAC 串行
PARALLELISM = 1

CSV_FILES = [
    "snn_tradeoff_max_norm.csv",
    "snn_tradeoff_data_based.csv",
]


# ===========================================================
# 核心计算函数
# ===========================================================

def compute_power(avg_spikes_l1, avg_spikes_l2,
                  p_if=P_IF_SINGLE_UW,
                  p_mac=P_MAC_SINGLE_UW,
                  mac_ops=MAC_OPS,
                  parallelism=PARALLELISM):
    """根据公式计算 SNN/ANN 功耗及节能百分比。

    Args:
        avg_spikes_l1: 第一层平均每张图片脉冲数
        avg_spikes_l2: 第二层平均每张图片脉冲数
        p_if: 单个 IF 神经元一次事件功耗系数（µW）
        p_mac: 单个 MAC 一次运算功耗系数（µW）
        mac_ops: 完整 ANN 前向推理的 MAC 操作总数
        parallelism: ANN 并行度（≥1）

    Returns:
        (p_snn, p_ann, saving_percent)
    """
    if parallelism <= 0:
        raise ValueError("parallelism 必须大于 0")

    total_avg_spikes = float(avg_spikes_l1) + float(avg_spikes_l2)
    p_snn = p_if * total_avg_spikes
    p_ann = p_mac * (mac_ops / parallelism)

    if p_ann == 0:
        raise ValueError("P_ANN_uW 为 0，无法计算节能百分比")

    saving_percent = (p_ann - p_snn) / p_ann * 100.0
    return p_snn, p_ann, saving_percent


# ===========================================================
# CSV 读写
# ===========================================================

def read_csv_with_comments(path):
    """读取 CSV，保留头部注释行。

    Returns:
        comments: 以 # 开头的行列表
        fieldnames: 表头列表
        rows: 数据行字典列表
    """
    comments = []
    data_lines = []

    with open(path, 'r', newline='', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#'):
                comments.append(line.rstrip('\n'))
            else:
                data_lines.append(line)

    if not data_lines:
        raise ValueError(f"CSV 文件没有有效表头/数据: {path}")

    reader = csv.DictReader(data_lines)
    fieldnames = list(reader.fieldnames)
    rows = list(reader)
    return comments, fieldnames, rows


def write_csv_with_comments(path, comments, fieldnames, rows):
    """写回 CSV，保留注释行。"""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        for c in comments:
            f.write(c + '\n')
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fill_csv(path,
             p_if=P_IF_SINGLE_UW,
             p_mac=P_MAC_SINGLE_UW,
             mac_ops=MAC_OPS,
             parallelism=PARALLELISM):
    """填充单个 CSV 的功耗列，原地更新。"""
    comments, fieldnames, rows = read_csv_with_comments(path)

    required = {'Avg_Spikes_L1', 'Avg_Spikes_L2'}
    if not required.issubset(set(fieldnames)):
        raise ValueError(f"CSV 缺少必要列: {required - set(fieldnames)}")

    power_cols = [
        'P_if_single_uW', 'P_mac_single_uW',
        'P_SNN_uW', 'P_ANN_uW', 'power_saving_percent'
    ]
    for col in power_cols:
        if col not in fieldnames:
            fieldnames.append(col)

    # 记录本次填充所用的实测值与假设，并清理旧假设行避免累积
    assumption_line = (
        f"# 实测功耗与 ANN 并行度假设："
        f"P_if={p_if}µW, P_mac={p_mac}µW, parallelism={parallelism}（单 MAC 串行基线）"
    )
    comments = [c for c in comments if not c.startswith("# 实测功耗与 ANN 并行度假设：")]
    if not any(assumption_line in c for c in comments):
        comments.append(assumption_line)

    for row in rows:
        p_snn, p_ann, saving = compute_power(
            row['Avg_Spikes_L1'], row['Avg_Spikes_L2'],
            p_if, p_mac, mac_ops, parallelism)
        row['P_if_single_uW'] = f"{p_if:.3f}"
        row['P_mac_single_uW'] = f"{p_mac:.3f}"
        row['P_SNN_uW'] = f"{p_snn:.3f}"
        row['P_ANN_uW'] = f"{p_ann:.3f}"
        row['power_saving_percent'] = f"{saving:.2f}"

    write_csv_with_comments(path, comments, fieldnames, rows)
    return rows


# ===========================================================
# 单元测试
# ===========================================================

def run_tests():
    """轻量级单元测试：覆盖正常路径、边界和异常分支。"""
    # 正常路径
    p_snn, p_ann, saving = compute_power(100.0, 20.0)
    assert abs(p_snn - P_IF_SINGLE_UW * 120.0) < 1e-9
    assert abs(p_ann - P_MAC_SINGLE_UW * MAC_OPS) < 1e-9
    assert 0.0 < saving < 100.0

    # 边界：SNN 脉冲数为 0
    p_snn, p_ann, saving = compute_power(0.0, 0.0)
    assert p_snn == 0.0
    assert saving == 100.0

    # 异常：并行度非法
    try:
        compute_power(1.0, 1.0, parallelism=0)
        assert False, "应抛出 ValueError"
    except ValueError:
        pass

    print("[测试通过] compute_power 正常/边界/异常场景均通过")


# ===========================================================
# 程序入口
# ===========================================================

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 60)
    print("  填充 SNN trade-off CSV 功耗列")
    print("=" * 60)
    print(f"Cadence 实测动态功耗：P_if_dyn={P_IF_DYNAMIC_UW} µW, "
          f"P_mac_dyn={P_MAC_DYNAMIC_UW} µW")
    print(f"Cadence 实测静态功耗：P_if_static={P_IF_STATIC_UW} µW, "
          f"P_mac_static={P_MAC_STATIC_UW} µW")
    print(f"用于计算的有效功耗：P_if={P_IF_SINGLE_UW:.6f} µW, "
          f"P_mac={P_MAC_SINGLE_UW:.6f} µW")
    print(f"网络：{INPUT_DIM}→{HIDDEN_DIM}→{OUTPUT_DIM}，总 MAC 运算={MAC_OPS}")
    print(f"ANN 并行度假设：parallelism={PARALLELISM}（单 MAC 串行）")
    print("=" * 60)

    for filename in CSV_FILES:
        path = os.path.join(base_dir, filename)
        if not os.path.exists(path):
            print(f"[跳过] 文件不存在: {path}")
            continue
        fill_csv(path)
        print(f"[已更新] {path}")

    print("\n[完成] 功耗列已填充，可直接用于后续作图/分析。")


if __name__ == "__main__":
    run_tests()
    main()
