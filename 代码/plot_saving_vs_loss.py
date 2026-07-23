#!/usr/bin/env python3
"""
plot_saving_vs_loss.py — 节能百分比 vs 准确率下降核心图
=========================================================
本课题最初的研究目的：量化 SNN 相比 ANN "每节省多少功耗，会损失多少准确率"。

生成：
  1. snn_saving_vs_loss_both.png — data_based 与 max_norm 同图对比
  2. snn_saving_vs_loss_data_based.png — data_based 单独详细图
  3. saving_loss_table.csv / .md — 关键配置点的节能、准确率下降及性价比
"""

import csv
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np


def set_chinese_font():
    """设置中文字体。"""
    candidates = [
        'PingFang SC', 'Hiragino Sans GB', 'STHeiti',
        'Microsoft YaHei', 'Arial Unicode MS', 'SimHei',
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for font in candidates:
        if font in available:
            plt.rcParams['font.sans-serif'] = [font]
            break
    plt.rcParams['axes.unicode_minus'] = False


set_chinese_font()


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLOTS_DIR = os.path.join(BASE_DIR, 'plots')
os.makedirs(PLOTS_DIR, exist_ok=True)


ANN_ACCURACY = 97.0


def read_csv(path):
    """读取 CSV，跳过注释行。"""
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(line for line in f if not line.startswith('#'))
        for row in reader:
            rows.append({k: float(v) for k, v in row.items()})
    return rows


def get_pareto(rows):
    """Pareto 前沿：不存在另一个点同时有更高准确率和更高节能百分比。"""
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
    pareto.sort(key=lambda r: r['power_saving_percent'])
    return pareto


def add_annotations(ax, pareto, x_key, y_key, color='darkred'):
    """标注 Pareto 点，使用自动偏移避免重叠。

    x_key / y_key 可以是列名字符串，也可以是接收 row 并返回数值的函数。
    """
    offsets = [
        (10, 8), (10, -14), (-10, 8), (-10, -14),
        (10, 22), (-10, 22), (10, -28), (-10, -28),
    ]
    for i, r in enumerate(pareto):
        x = r[x_key] if isinstance(x_key, str) else x_key(r)
        y = r[y_key] if isinstance(y_key, str) else y_key(r)
        dx, dy = offsets[i % len(offsets)]
        ax.annotate(
            f"T={int(r['T'])}, Vth={r['Vth']}",
            (x, y),
            textcoords='offset points', xytext=(dx, dy),
            fontsize=8, color=color, fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.25', fc='white', ec='none', alpha=0.85),
            arrowprops=dict(arrowstyle='->', color=color, lw=0.6, alpha=0.6)
        )


def plot_data_based(rows, output_path):
    """data_based 单独图：节能百分比 vs 准确率下降。"""
    pareto = get_pareto(rows)

    fig, ax = plt.subplots(figsize=(11, 7))

    # 全部点
    ax.scatter(
        [r['power_saving_percent'] for r in rows],
        [ANN_ACCURACY - r['Accuracy(%)'] for r in rows],
        c='lightblue', s=50, alpha=0.5, edgecolors='black', linewidth=0.4,
        label='全部配置'
    )

    # Pareto 前沿
    ax.plot(
        [r['power_saving_percent'] for r in pareto],
        [ANN_ACCURACY - r['Accuracy(%)'] for r in pareto],
        'r-', linewidth=3, marker='s', markersize=9,
        label='Pareto 前沿', zorder=5
    )

    # 关键参考点
    best_acc = max(rows, key=lambda r: r['Accuracy(%)'])
    best_save = max(rows, key=lambda r: r['power_saving_percent'])
    knee = min(
        [r for r in pareto if r['Accuracy(%)'] >= 95.0],
        key=lambda r: r['power_saving_percent']
    )

    highlights = [
        (best_acc, 'darkgreen', '最高准确率'),
        (knee, 'darkorange', '拐点 (knee)'),
        (best_save, 'purple', '最大节能'),
    ]
    for r, color, label in highlights:
        ax.scatter(
            r['power_saving_percent'],
            ANN_ACCURACY - r['Accuracy(%)'],
            c=color, s=140, marker='*', zorder=6,
            edgecolors='black', linewidth=0.6, label=label
        )

    add_annotations(ax, pareto, 'power_saving_percent',
                    lambda r: ANN_ACCURACY - r['Accuracy(%)'])

    ax.set_xlabel('相对 ANN 的节能百分比 (%)', fontsize=13)
    ax.set_ylabel('相对 ANN 的准确率下降 (%)', fontsize=13)
    ax.set_title('SNN 节能百分比 vs 准确率下降 [data_based 归一化]\n'
                 '（本课题核心研究问题：每省多少功耗，损失多少准确率）',
                 fontsize=14)
    ax.legend(fontsize=11, loc='upper left')
    ax.grid(True, alpha=0.3)

    # 在图上用文字框标注拐点信息
    textstr = (
        f"拐点推荐: T={int(knee['T'])}, Vth={knee['Vth']}\n"
        f"节能 {knee['power_saving_percent']:.2f}%, "
        f"准确率下降 {ANN_ACCURACY - knee['Accuracy(%)']:.2f}%"
    )
    ax.text(
        0.97, 0.08, textstr, transform=ax.transAxes,
        fontsize=11, verticalalignment='bottom', horizontalalignment='right',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8)
    )

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f'[图表保存] {output_path}')


def plot_both(data_based, max_norm, output_path):
    """data_based 与 max_norm 同图对比。"""
    pareto_db = get_pareto(data_based)
    pareto_mn = get_pareto(max_norm)

    fig, ax = plt.subplots(figsize=(12, 7))

    # 全部点（浅色）
    ax.scatter(
        [r['power_saving_percent'] for r in data_based],
        [ANN_ACCURACY - r['Accuracy(%)'] for r in data_based],
        c='lightblue', s=40, alpha=0.4, edgecolors='black', linewidth=0.3,
        label='data_based 全部配置'
    )
    ax.scatter(
        [r['power_saving_percent'] for r in max_norm],
        [ANN_ACCURACY - r['Accuracy(%)'] for r in max_norm],
        c='lightgreen', s=40, alpha=0.4, edgecolors='black', linewidth=0.3,
        label='max_norm 全部配置'
    )

    # Pareto 前沿
    ax.plot(
        [r['power_saving_percent'] for r in pareto_db],
        [ANN_ACCURACY - r['Accuracy(%)'] for r in pareto_db],
        'b-', linewidth=3, marker='o', markersize=8,
        label='data_based Pareto 前沿', zorder=5
    )
    ax.plot(
        [r['power_saving_percent'] for r in pareto_mn],
        [ANN_ACCURACY - r['Accuracy(%)'] for r in pareto_mn],
        'g-', linewidth=3, marker='s', markersize=8,
        label='max_norm Pareto 前沿', zorder=5
    )

    # 标注关键点（只标前 5 个，避免太乱）
    for i, r in enumerate(pareto_db[:5]):
        ax.annotate(
            f"T={int(r['T'])}, Vth={r['Vth']}",
            (r['power_saving_percent'], ANN_ACCURACY - r['Accuracy(%)']),
            textcoords='offset points', xytext=(10, 8 if i % 2 == 0 else -14),
            fontsize=8, color='darkblue', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.8)
        )
    for i, r in enumerate(pareto_mn[:5]):
        ax.annotate(
            f"T={int(r['T'])}, Vth={r['Vth']}",
            (r['power_saving_percent'], ANN_ACCURACY - r['Accuracy(%)']),
            textcoords='offset points', xytext=(-10, 8 if i % 2 == 0 else -14),
            fontsize=8, color='darkgreen', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='none', alpha=0.8)
        )

    ax.set_xlabel('相对 ANN 的节能百分比 (%)', fontsize=13)
    ax.set_ylabel('相对 ANN 的准确率下降 (%)', fontsize=13)
    ax.set_title('SNN 节能百分比 vs 准确率下降：data_based vs max_norm\n'
                 '（越靠左上越好：高节能 + 低准确率损失）',
                 fontsize=14)
    ax.legend(fontsize=11, loc='upper left')
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f'[图表保存] {output_path}')


def make_table(rows, method_name):
    """生成对比表数据。"""
    pareto = get_pareto(rows)
    records = []
    for r in pareto:
        acc_loss = ANN_ACCURACY - r['Accuracy(%)']
        saving = r['power_saving_percent']
        # 每损失 1% 准确率带来的节能增益
        roi = saving / acc_loss if acc_loss > 0 else float('inf')
        records.append({
            'method': method_name,
            'T': int(r['T']),
            'Vth': r['Vth'],
            '节能百分比': saving,
            '准确率下降': acc_loss,
            '节能_准确率损失比': roi,
            'SNN/ANN能耗比': 100 * r['P_SNN_uW'] / r['P_ANN_uW'],
            'Accuracy': r['Accuracy(%)'],
        })
    return records


def write_table(records, csv_path, md_path):
    """保存 CSV 和 Markdown 表格。"""
    fieldnames = [
        'method', 'T', 'Vth', 'Accuracy', '节能百分比',
        '准确率下降', '节能_准确率损失比', 'SNN/ANN能耗比'
    ]
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f'[CSV 保存] {csv_path}')

    lines = []
    lines.append('| 方法 | T | Vth | 准确率(%) | 节能(%) | 准确率下降(%) | '
                 '节能/下降比 | SNN/ANN(%) |')
    lines.append('|---|---|---|---|---|---|---|---|')
    for rec in records:
        lines.append(
            f"| {rec['method']} | {rec['T']} | {rec['Vth']:.2f} | "
            f"{rec['Accuracy']:.1f} | {rec['节能百分比']:.2f} | "
            f"{rec['准确率下降']:.2f} | {rec['节能_准确率损失比']:.1f} | "
            f"{rec['SNN/ANN能耗比']:.3f} |"
        )
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print(f'[Markdown 保存] {md_path}')


def main():
    data_dir = os.path.join(BASE_DIR, 'data')
    tables_dir = os.path.join(BASE_DIR, 'tables')
    os.makedirs(tables_dir, exist_ok=True)

    data_based = read_csv(os.path.join(data_dir, 'snn_tradeoff_data_based.csv'))
    max_norm = read_csv(os.path.join(data_dir, 'snn_tradeoff_max_norm.csv'))

    plot_data_based(
        data_based,
        os.path.join(PLOTS_DIR, 'snn_saving_vs_loss_data_based.png')
    )
    plot_both(
        data_based, max_norm,
        os.path.join(PLOTS_DIR, 'snn_saving_vs_loss_both.png')
    )

    records = []
    records.extend(make_table(data_based, 'data_based'))
    records.extend(make_table(max_norm, 'max_norm'))

    write_table(
        records,
        os.path.join(tables_dir, 'saving_loss_table.csv'),
        os.path.join(tables_dir, 'saving_loss_table.md')
    )


if __name__ == '__main__':
    main()
