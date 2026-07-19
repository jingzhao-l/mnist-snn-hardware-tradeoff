#!/usr/bin/env python3
"""
plot_power_tradeoff.py — 绘制 SNN vs ANN 功耗-准确率权衡曲线
===========================================================
基于已经填好功耗列的 CSV（snn_tradeoff_*.csv），画出：
  1. 准确率 vs SNN 推理能耗（对数坐标）
  2. 准确率 vs 相对 ANN 的节能百分比
  3. 准确率-SNN 能耗 Pareto 前沿散点图
  4. 准确率-节能百分比 Pareto 前沿散点图
  5. SNN/ANN 能耗比 vs 准确率

这些图可以直接说明：每让 SNN 多省一点功耗，会损失多少准确率。
"""

import csv
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np


def set_chinese_font():
    """尝试设置一个支持中文的字体，避免图表中中文乱码。"""
    candidates = [
        'PingFang SC',
        'Hiragino Sans GB',
        'STHeiti',
        'Microsoft YaHei',
        'Arial Unicode MS',
        'SimHei',
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            plt.rcParams['font.sans-serif'] = [font]
            break
    plt.rcParams['axes.unicode_minus'] = False


set_chinese_font()


def read_csv(path):
    """读取 trade-off CSV，跳过注释行，返回字典列表。"""
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(line for line in f if not line.startswith('#'))
        for row in reader:
            rows.append({k: float(v) for k, v in row.items()})
    return rows


def get_pareto_frontier(rows):
    """求 Pareto 前沿：不存在另一个点同时有更高准确率和更高节能百分比。"""
    pts = [(r['power_saving_percent'], r['Accuracy(%)'], r) for r in rows]
    pareto = []
    for s, a, r in pts:
        dominated = False
        for s2, a2, _ in pts:
            if s2 >= s and a2 >= a and (s2 > s or a2 > a):
                dominated = True
                break
        if not dominated:
            pareto.append(r)
    # 按节能百分比排序，方便连线
    pareto.sort(key=lambda r: r['power_saving_percent'])
    return pareto


def plot_accuracy_vs_power(rows, p_ann, norm_method, output_dir):
    """图 1：准确率 vs SNN 推理能耗 P_SNN_uW（对数坐标）。"""
    vth_values = sorted({r['Vth'] for r in rows})
    colors = plt.cm.viridis(np.linspace(0, 0.9, len(vth_values)))

    fig, ax = plt.subplots(figsize=(10, 6))
    for vi, vth in enumerate(vth_values):
        subset = [r for r in rows if r['Vth'] == vth]
        subset.sort(key=lambda r: r['P_SNN_uW'])
        ax.plot(
            [r['P_SNN_uW'] for r in subset],
            [r['Accuracy(%)'] for r in subset],
            marker='o', linewidth=2, markersize=7,
            color=colors[vi], label=f'Vth = {vth:.2f}'
        )

    ax.axvline(p_ann, color='red', linestyle='--', linewidth=1.5,
               label=f'ANN 参考能耗 = {p_ann/1e3:.1f} mW·cycle')
    ax.axhline(97.0, color='gray', linestyle=':', linewidth=1,
               label='ANN 参考准确率 ~97%')

    ax.set_xscale('log')
    ax.set_xlabel('SNN 一次推理能耗 P_SNN (µW·cycle)', fontsize=12)
    ax.set_ylabel('测试准确率 (%)', fontsize=12)
    ax.set_title(f'SNN 准确率 vs 推理能耗 [{norm_method} 归一化]', fontsize=14)
    ax.legend(fontsize=9)
    ax.grid(True, which='both', alpha=0.3)

    path = os.path.join(output_dir, f'snn_accuracy_vs_power_{norm_method}.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f'[图表保存] 准确率 vs 能耗: {path}')


def plot_accuracy_vs_saving(rows, norm_method, output_dir):
    """图 2：准确率 vs 相对 ANN 的节能百分比。"""
    vth_values = sorted({r['Vth'] for r in rows})
    colors = plt.cm.plasma(np.linspace(0, 0.9, len(vth_values)))

    fig, ax = plt.subplots(figsize=(10, 6))
    for vi, vth in enumerate(vth_values):
        subset = [r for r in rows if r['Vth'] == vth]
        subset.sort(key=lambda r: r['power_saving_percent'])
        ax.plot(
            [r['power_saving_percent'] for r in subset],
            [r['Accuracy(%)'] for r in subset],
            marker='s', linewidth=2, markersize=7,
            color=colors[vi], label=f'Vth = {vth:.2f}'
        )

    ax.axhline(97.0, color='gray', linestyle=':', linewidth=1,
               label='ANN 参考准确率 ~97%')

    ax.set_xlabel('相对 ANN 的节能百分比 (%)', fontsize=12)
    ax.set_ylabel('测试准确率 (%)', fontsize=12)
    ax.set_title(f'SNN 准确率 vs 节能百分比 [{norm_method} 归一化]',
                 fontsize=14)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    path = os.path.join(output_dir, f'snn_accuracy_vs_saving_{norm_method}.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f'[图表保存] 准确率 vs 节能: {path}')


def plot_pareto_frontier(rows, p_ann, norm_method, output_dir):
    """图 3：Pareto 前沿散点图（x=能耗，y=准确率）。"""
    pareto = get_pareto_frontier(rows)

    fig, ax = plt.subplots(figsize=(10, 7))
    vth_values = sorted({r['Vth'] for r in rows})
    cmap = plt.cm.viridis
    norm = plt.Normalize(vmin=min(vth_values), vmax=max(vth_values))

    for r in rows:
        ax.scatter(
            r['P_SNN_uW'], r['Accuracy(%)'],
            c=[r['Vth']], cmap=cmap, norm=norm,
            s=r['T'] * 1.5 + 30, alpha=0.6,
            edgecolors='black', linewidth=0.5
        )

    # Pareto 前沿连线
    ax.plot([r['P_SNN_uW'] for r in pareto],
            [r['Accuracy(%)'] for r in pareto],
            'r--', linewidth=2, label='Pareto 前沿')

    # ANN 参考点
    ax.scatter(p_ann, 97.0, c='red', s=150, marker='X',
               label='ANN 参考', zorder=5)

    cbar = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax)
    cbar.set_label('阈值 Vth', fontsize=11)

    ax.set_xscale('log')
    ax.set_xlabel('SNN 一次推理能耗 P_SNN (µW·cycle)', fontsize=12)
    ax.set_ylabel('测试准确率 (%)', fontsize=12)
    ax.set_title(f'SNN 能耗-准确率 Pareto 前沿 [{norm_method} 归一化]\n'
                 '(点越大 = T 越大，颜色 = Vth)', fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, which='both', alpha=0.3)

    path = os.path.join(output_dir, f'snn_pareto_power_{norm_method}.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f'[图表保存] Pareto 前沿（能耗）: {path}')


def plot_saving_pareto(rows, norm_method, output_dir):
    """图 4：节能百分比-准确率 Pareto 前沿散点图。"""
    pareto = get_pareto_frontier(rows)

    fig, ax = plt.subplots(figsize=(10, 7))
    vth_values = sorted({r['Vth'] for r in rows})
    cmap = plt.cm.plasma
    norm = plt.Normalize(vmin=min(vth_values), vmax=max(vth_values))

    for r in rows:
        ax.scatter(
            r['power_saving_percent'], r['Accuracy(%)'],
            c=[r['Vth']], cmap=cmap, norm=norm,
            s=r['T'] * 1.5 + 30, alpha=0.6,
            edgecolors='black', linewidth=0.5
        )

    ax.plot([r['power_saving_percent'] for r in pareto],
            [r['Accuracy(%)'] for r in pareto],
            'r--', linewidth=2, label='Pareto 前沿')

    ax.axvline(0, color='gray', linestyle=':', linewidth=1)
    ax.axhline(97.0, color='gray', linestyle=':', linewidth=1,
               label='ANN 参考准确率 ~97%')

    cbar = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=ax)
    cbar.set_label('阈值 Vth', fontsize=11)

    ax.set_xlabel('相对 ANN 的节能百分比 (%)', fontsize=12)
    ax.set_ylabel('测试准确率 (%)', fontsize=12)
    ax.set_title(f'SNN 节能百分比-准确率 Pareto 前沿 [{norm_method} 归一化]\n'
                 '(理想点在右上角：高准确率 + 高节能)', fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    path = os.path.join(output_dir, f'snn_pareto_saving_{norm_method}.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f'[图表保存] Pareto 前沿（节能）: {path}')


def plot_energy_ratio(rows, norm_method, output_dir):
    """图 5：SNN/ANN 能耗比 vs 准确率（Y 轴对数，便于看清数量级差异）。"""
    fig, ax = plt.subplots(figsize=(10, 6))
    vth_values = sorted({r['Vth'] for r in rows})
    colors = plt.cm.coolwarm(np.linspace(0, 0.9, len(vth_values)))

    for vi, vth in enumerate(vth_values):
        subset = [r for r in rows if r['Vth'] == vth]
        subset.sort(key=lambda r: r['Accuracy(%)'])
        ratios = [100 * r['P_SNN_uW'] / r['P_ANN_uW'] for r in subset]
        ax.plot(
            [r['Accuracy(%)'] for r in subset],
            ratios,
            marker='^', linewidth=2, markersize=7,
            color=colors[vi], label=f'Vth = {vth:.2f}'
        )

    ax.axhline(100, color='red', linestyle='--', linewidth=1.5,
               label='SNN 能耗 = ANN 能耗')

    ax.set_yscale('log')
    ax.set_xlabel('测试准确率 (%)', fontsize=12)
    ax.set_ylabel('SNN 能耗 / ANN 能耗 (%)', fontsize=12)
    ax.set_title(f'SNN 相对 ANN 能耗比 vs 准确率 [{norm_method} 归一化]',
                 fontsize=14)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, which='both')

    path = os.path.join(output_dir, f'snn_energy_ratio_{norm_method}.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f'[图表保存] 能耗比 vs 准确率: {path}')


def plot_tradeoff_curve(rows, norm_method, output_dir):
    """图 6：核心 trade-off 曲线。

    横轴 = SNN 能耗 / ANN 能耗（对数坐标），纵轴 = 准确率。
    同一条 Vth 曲线上，T 从 5 到 100 逐渐向右上方移动。
    这条图最直观地回答：每多耗一点能量，能换多少准确率。
    """
    fig, ax = plt.subplots(figsize=(11, 7))
    vth_values = sorted({r['Vth'] for r in rows})
    colors = plt.cm.viridis(np.linspace(0, 0.9, len(vth_values)))

    for vi, vth in enumerate(vth_values):
        subset = [r for r in rows if r['Vth'] == vth]
        subset.sort(key=lambda r: r['T'])
        ratios = [100 * r['P_SNN_uW'] / r['P_ANN_uW'] for r in subset]
        accs = [r['Accuracy(%)'] for r in subset]
        ax.plot(ratios, accs, marker='o', linewidth=2.5, markersize=7,
                color=colors[vi], label=f'Vth = {vth:.2f}')
    # Pareto 前沿
    pareto = get_pareto_frontier(rows)
    pareto.sort(key=lambda r: r['P_SNN_uW'] / r['P_ANN_uW'])
    ax.plot(
        [100 * r['P_SNN_uW'] / r['P_ANN_uW'] for r in pareto],
        [r['Accuracy(%)'] for r in pareto],
        'r--', linewidth=2.5, marker='s', markersize=8,
        label='Pareto 前沿', zorder=5
    )

    ax.axhline(97.0, color='gray', linestyle=':', linewidth=1.2,
               label='ANN 参考准确率 ~97%')
    ax.axvline(100.0, color='gray', linestyle=':', linewidth=1.2,
               label='SNN 能耗 = ANN 能耗')

    ax.set_xscale('log')
    ax.set_xlabel('SNN 能耗 / ANN 能耗 (%) — 越小越省电', fontsize=12)
    ax.set_ylabel('测试准确率 (%)', fontsize=12)
    ax.set_title(f'SNN 能耗-准确率 trade-off 曲线 [{norm_method} 归一化]\n'
                 '（同一条曲线上 T 从左到右递增）', fontsize=14)
    ax.legend(fontsize=9, loc='lower right')
    ax.grid(True, alpha=0.3, which='both')

    path = os.path.join(output_dir, f'snn_tradeoff_curve_{norm_method}.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f'[图表保存] 核心 trade-off 曲线: {path}')


def plot_pareto_labeled(rows, norm_method, output_dir):
    """图 7：仅展示 Pareto 前沿点，并标注 (T, Vth)，避免数据重叠。"""
    pareto = get_pareto_frontier(rows)

    fig, ax = plt.subplots(figsize=(10, 7))

    # 画所有点（浅色、小）
    ax.scatter(
        [r['P_SNN_uW'] for r in rows],
        [r['Accuracy(%)'] for r in rows],
        c='lightgray', s=40, alpha=0.5, label='全部配置'
    )

    # Pareto 点（深色、大）
    ax.scatter(
        [r['P_SNN_uW'] for r in pareto],
        [r['Accuracy(%)'] for r in pareto],
        c='red', s=120, zorder=5, label='Pareto 前沿'
    )

    offsets = [(8, 6), (8, -14), (-8, 6), (-8, -14), (8, 22), (-8, 22)]
    for i, r in enumerate(pareto):
        dx, dy = offsets[i % len(offsets)]
        ax.annotate(
            f"T={int(r['T'])}, Vth={r['Vth']}",
            (r['P_SNN_uW'], r['Accuracy(%)']),
            textcoords='offset points', xytext=(dx, dy),
            fontsize=9, color='darkred', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.7)
        )

    ax.set_xscale('log')
    ax.set_xlabel('SNN 一次推理能耗 P_SNN (µW·cycle)', fontsize=12)
    ax.set_ylabel('测试准确率 (%)', fontsize=12)
    ax.set_title(f'SNN Pareto 前沿配置 [{norm_method} 归一化]',
                 fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, which='both')

    path = os.path.join(output_dir, f'snn_pareto_labeled_{norm_method}.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f'[图表保存] 带标注的 Pareto 前沿: {path}')


def plot_pareto_table(rows, norm_method, output_dir):
    """图 8：把 Pareto 前沿配置以表格形式输出，避免散点图重叠。"""
    pareto = get_pareto_frontier(rows)
    pareto.sort(key=lambda r: r['P_SNN_uW'])

    fig, ax = plt.subplots(figsize=(10, 0.6 * len(pareto) + 1.5))
    ax.axis('off')
    ax.axis('tight')

    columns = ['T', 'Vth', 'Accuracy(%)', '节能(%)', 'P_SNN(mW·cycle)']
    cell_data = []
    for r in pareto:
        cell_data.append([
            f"{int(r['T'])}",
            f"{r['Vth']:.2f}",
            f"{r['Accuracy(%)']:.1f}",
            f"{r['power_saving_percent']:.2f}",
            f"{r['P_SNN_uW'] / 1e3:.3f}",
        ])

    table = ax.table(
        cellText=cell_data, colLabels=columns,
        loc='center', cellLoc='center',
        colColours=['#4472C4'] * len(columns),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 2)

    # 表头白色字体
    for key, cell in table.get_celld().items():
        row, col = key
        if row == 0:
            cell.set_text_props(color='white', fontweight='bold')
            cell.set_facecolor('#4472C4')
        else:
            cell.set_facecolor('#F2F2F2' if row % 2 == 0 else 'white')

    ax.set_title(f'SNN Pareto 前沿配置表 [{norm_method} 归一化]',
                 fontsize=14, pad=20)

    path = os.path.join(output_dir, f'snn_pareto_table_{norm_method}.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'[图表保存] Pareto 配置表: {path}')


def plot_saving_vs_loss(rows, norm_method, output_dir):
    """图 8：节能百分比 vs 准确率下降（Pareto 前沿专用）。

    横轴 = (ANN 能耗 - SNN 能耗) / ANN 能耗 × 100，
    纵轴 = ANN 参考准确率 - SNN 准确率。
    只画 Pareto 前沿，并标注 (T, Vth)，避免全部数据叠在一起。
    """
    pareto = get_pareto_frontier(rows)
    pareto.sort(key=lambda r: r['power_saving_percent'])

    fig, ax = plt.subplots(figsize=(10, 7))

    # 全部点作为浅色背景，方便定位 Pareto 点在整个空间中的位置
    ax.scatter(
        [r['power_saving_percent'] for r in rows],
        [97.0 - r['Accuracy(%)'] for r in rows],
        c='lightgray', s=40, alpha=0.5, label='全部配置'
    )

    # Pareto 前沿：红色带方块标记
    ax.plot(
        [r['power_saving_percent'] for r in pareto],
        [97.0 - r['Accuracy(%)'] for r in pareto],
        'r-', linewidth=3, marker='s', markersize=9,
        label='Pareto 前沿', zorder=5
    )

    # 标注每个 Pareto 点的 (T, Vth)，交替偏移避免重叠
    offsets = [(8, 6), (8, -16), (-8, 6), (-8, -16), (8, 26), (-8, 26)]
    for i, r in enumerate(pareto):
        dx, dy = offsets[i % len(offsets)]
        ax.annotate(
            f"T={int(r['T'])}, Vth={r['Vth']}",
            (r['power_saving_percent'], 97.0 - r['Accuracy(%)']),
            textcoords='offset points', xytext=(dx, dy),
            fontsize=9, color='darkred', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.8)
        )

    ax.set_xlabel('相对 ANN 的节能百分比 (%)', fontsize=12)
    ax.set_ylabel('相对 ANN 的准确率下降 (%)', fontsize=12)
    ax.set_title(f'SNN 节能百分比 vs 准确率下降 [{norm_method} 归一化]\n'
                 '（Pareto 前沿：每多省一点功耗，会损失多少准确率）',
                 fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    # 放大到 Pareto 前沿附近，避免大片空白
    min_save = min(r['power_saving_percent'] for r in pareto)
    max_save = max(r['power_saving_percent'] for r in pareto)
    max_loss = max(97.0 - r['Accuracy(%)'] for r in pareto)
    ax.set_xlim(min_save - 1.5, 100.0)
    ax.set_ylim(-0.5, max_loss + 1.5)

    path = os.path.join(output_dir, f'snn_saving_vs_loss_{norm_method}.png')
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f'[图表保存] 节能 vs 准确率下降: {path}')


def print_summary(rows, norm_method, p_ann):
    """打印关键配置。"""
    best_acc = max(rows, key=lambda r: r['Accuracy(%)'])
    best_save = max(rows, key=lambda r: r['power_saving_percent'])
    best_ratio = min(rows, key=lambda r: r['P_SNN_uW'] / r['P_ANN_uW'])

    print(f'\n=== {norm_method} ===')
    print(f'ANN 参考能耗: {p_ann/1e3:.2f} mW·cycle')
    print(f'最高准确率: T={int(best_acc["T"])}, Vth={best_acc["Vth"]}, '
          f'Acc={best_acc["Accuracy(%)"]}%, '
          f'P_SNN={best_acc["P_SNN_uW"]/1e3:.2f} mW·cycle, '
          f'节能={best_acc["power_saving_percent"]:.2f}%')
    print(f'最大节能: T={int(best_save["T"])}, Vth={best_save["Vth"]}, '
          f'Acc={best_save["Accuracy(%)"]}%, '
          f'节能={best_save["power_saving_percent"]:.2f}%')
    print(f'最低能耗比: T={int(best_ratio["T"])}, Vth={best_ratio["Vth"]}, '
          f'Acc={best_ratio["Accuracy(%)"]}%, '
          f'SNN/ANN={100*best_ratio["P_SNN_uW"]/best_ratio["P_ANN_uW"]:.2f}%')

    pareto = get_pareto_frontier(rows)
    print(f'\nPareto 前沿上的配置（{len(pareto)} 个）：')
    for r in pareto:
        print(f'  T={int(r["T"]):>3}, Vth={r["Vth"]:>5}, '
              f'Acc={r["Accuracy(%)"]:>5}%, '
              f'节能={r["power_saving_percent"]:>6.2f}%, '
              f'P_SNN={r["P_SNN_uW"]/1e3:>7.3f} mW·cycle')


def process_one_csv(csv_path, output_dir):
    """处理单个 CSV 并生成全部图表。"""
    rows = read_csv(csv_path)
    if not rows:
        print(f'[错误] 没有读到数据: {csv_path}')
        return

    # 从文件名推断归一化方法
    basename = os.path.basename(csv_path)
    if 'data_based' in basename:
        norm_method = 'data_based'
    elif 'max_norm' in basename:
        norm_method = 'max_norm'
    else:
        norm_method = 'unknown'

    p_ann = rows[0]['P_ANN_uW']
    os.makedirs(output_dir, exist_ok=True)

    plot_accuracy_vs_power(rows, p_ann, norm_method, output_dir)
    plot_accuracy_vs_saving(rows, norm_method, output_dir)
    plot_pareto_frontier(rows, p_ann, norm_method, output_dir)
    plot_saving_pareto(rows, norm_method, output_dir)
    plot_energy_ratio(rows, norm_method, output_dir)
    plot_tradeoff_curve(rows, norm_method, output_dir)
    plot_pareto_table(rows, norm_method, output_dir)
    plot_saving_vs_loss(rows, norm_method, output_dir)
    print_summary(rows, norm_method, p_ann)


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_files = [
        os.path.join(base_dir, 'snn_tradeoff_data_based.csv'),
        os.path.join(base_dir, 'snn_tradeoff_max_norm.csv'),
    ]
    output_dir = os.path.join(base_dir, 'plots')

    for csv_path in csv_files:
        if not os.path.exists(csv_path):
            print(f'[跳过] 文件不存在: {csv_path}')
            continue
        process_one_csv(csv_path, output_dir)


if __name__ == '__main__':
    main()
