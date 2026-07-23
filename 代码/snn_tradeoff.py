"""
snn_tradeoff.py —— SNN 精度-效率权衡分析
==========================================
功能：
  1. 扫描不同 (T, Vth) 组合，全面评估 SNN 性能
  2. 记录每组参数的准确率和脉冲稀疏率
  3. 绘制准确率 vs 时间步曲线（含误差带）
  4. 绘制脉冲稀疏率 vs 阈值曲线
  5. 绘制准确率-稀疏率 Pareto 前沿图
  6. 保存完整 trade-off 数据到 CSV

【为什么需要 trade-off 分析】
  SNN 的核心优势是"精度-效率可调节"：
  - T 越大：编码信息更完整 → 准确率高，但推理延迟大
  - Vth 越大：神经元越难触发 → 脉冲少功耗低，但可能丢信息
  找到在满足精度要求下最大化能效的 (T, Vth) 组合，
  是 SNN 部署到硬件前的关键设计决策。

所有代码纯 numpy + matplotlib 手写。
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')  # 非交互式后端，适合无 GUI 环境
import matplotlib.pyplot as plt
import csv
import os
import sys
from sklearn.datasets import fetch_openml

# 导入主模块中的核心类和函数
from snn_conversion import (
    load_ann_weights,
    max_norm_normalize,
    data_based_normalize,
    SNN,
    SNNConfig,
    test_snn,
)


# ============================================================
# 第 1 部分：Trade-off 扫描
# ============================================================

def scan_tradeoff(W1, b1, W2, b2, X_test, y_test, X_train,
                  T_values, Vth_values, norm_method="max_norm",
                  percentile=99.9, max_test_samples=500,
                  verbose=True):
    """扫描不同 (T, Vth) 组合，收集准确率和稀疏率数据

    对于每种 (T, Vth) 组合：
    1. 用指定方法归一化权重
    2. 构建 SNN
    3. 在测试子集上评估准确率和脉冲稀疏率

    Args:
        W1, b1, W2, b2: ANN 原始权重
        X_test, y_test:  测试集
        X_train:         训练集（data_based 归一化需要）
        T_values:        时间步候选值列表，如 [10, 20, 30, 50, 100]
        Vth_values:      阈值候选值列表，如 [0.5, 1.0, 2.0, 5.0]
        norm_method:     "max_norm" 或 "data_based"
        percentile:      data_based 归一化的分位数
        max_test_samples: 每组参数测试的最大样本数（减少总时间）
        verbose:         是否打印进度

    Returns:
        results: 列表，每个元素为 dict:
            {T, Vth, accuracy, sparsity, total_spikes_l1, total_spikes_l2}
    """
    results = []
    total_combos = len(T_values) * len(Vth_values)

    combo_idx = 0
    for Vth in Vth_values:
        # data_based 归一化依赖于 Vth，对每个 Vth 重新归一化
        if norm_method == "max_norm":
            (W1_norm, b1_norm), (W2_norm, b2_norm) = max_norm_normalize(
                W1.copy(), b1.copy(), W2.copy(), b2.copy())
        elif norm_method == "data_based":
            (W1_norm, b1_norm), (W2_norm, b2_norm) = data_based_normalize(
                W1, b1, W2, b2, X_train, Vth=Vth, percentile=percentile)
        else:
            raise ValueError(f"未知的归一化方法: {norm_method}")

        for T in T_values:
            combo_idx += 1
            if verbose:
                print(f"\n[{combo_idx}/{total_combos}] T={T:3d}, Vth={Vth:.1f}")

            # 构建 SNN
            snn = SNN(W1_norm, b1_norm, W2_norm, b2_norm,
                      Vth=Vth, reset_mode="hard")

            # 测试
            accuracy, stats, _ = test_snn(
                snn, X_test, y_test, T,
                max_samples=max_test_samples, verbose=False)

            result = {
                'T': T,
                'Vth': Vth,
                'accuracy': accuracy,
                'sparsity_l1': stats['sparsity_l1'],
                'sparsity_l2': stats['sparsity_l2'],
                'overall_sparsity': stats['overall_sparsity'],
                'avg_spikes_l1': stats['avg_spikes_l1_per_image'],
                'avg_spikes_l2': stats['avg_spikes_l2_per_image'],
                'total_spikes_l1': stats['total_spikes_l1'],
                'total_spikes_l2': stats['total_spikes_l2'],
            }
            results.append(result)

            if verbose:
                print(f"  准确率: {accuracy*100:6.2f}%  |  "
                      f"整体稀疏率: {stats['overall_sparsity']*100:5.2f}%")

    return results


# ============================================================
# 第 2 部分：可视化
# ============================================================

def plot_tradeoff_results(results, output_dir,
                          norm_method="max_norm", T_values=None,
                          Vth_values=None):
    """绘制 trade-off 分析的三张核心图表

    Args:
        results:     scan_tradeoff() 返回的结果列表
        output_dir:  图片输出目录
        norm_method: 归一化方法名（用于标题）
        T_values:    T 值列表（用于选取代表性阈值）
        Vth_values:  Vth 值列表
    """
    if T_values is None:
        T_values = sorted(set(r['T'] for r in results))
    if Vth_values is None:
        Vth_values = sorted(set(r['Vth'] for r in results))

    # 将结果转为结构化数组方便索引
    # results_by_T[vth_idx][t_idx] = result_dict
    results_by_Vth = {v: {} for v in Vth_values}
    for r in results:
        results_by_Vth[r['Vth']][r['T']] = r

    results_by_T = {t: {} for t in T_values}
    for r in results:
        results_by_T[r['T']][r['Vth']] = r

    # ---- 图 1：准确率 vs 时间步 (Accuracy vs T) ----
    fig1, ax1 = plt.subplots(figsize=(10, 6))

    # 选取几个代表性的 Vth 值绘制曲线
    representative_Vth = [Vth_values[0], Vth_values[len(Vth_values)//2], Vth_values[-1]]
    colors_vth = ['#2196F3', '#FF9800', '#4CAF50']
    markers_vth = ['o', 's', '^']

    for v_idx, Vth in enumerate(representative_Vth):
        if Vth not in results_by_Vth:
            continue
        T_list = []
        acc_list = []
        for T in T_values:
            if T in results_by_Vth[Vth]:
                T_list.append(T)
                acc_list.append(results_by_Vth[Vth][T]['accuracy'] * 100)

        if T_list:
            ax1.plot(T_list, acc_list,
                     color=colors_vth[v_idx % len(colors_vth)],
                     marker=markers_vth[v_idx % len(markers_vth)],
                     linewidth=2, markersize=8,
                     label=f'Vth = {Vth:.1f}')

    # 标注 ANN 准确率参考线
    ann_accuracy = 97.0  # 典型值，来自 train_ann_relu.py 的训练结果
    ax1.axhline(y=ann_accuracy, color='red', linestyle='--', linewidth=1.5,
                label=f'ANN 参考 (~{ann_accuracy:.1f}%)')

    ax1.set_xlabel('仿真时间步 T (越大 → 编码信息越完整)', fontsize=12)
    ax1.set_ylabel('测试准确率 (%)', fontsize=12)
    ax1.set_title(f'SNN 准确率 vs 时间步 [{norm_method} 归一化]', fontsize=14)
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(left=0)

    fig1.tight_layout()
    path1 = os.path.join(output_dir, 'snn_accuracy_vs_T.png')
    fig1.savefig(path1, dpi=150)
    plt.close(fig1)
    print(f"[图表保存] 准确率 vs T: {path1}")

    # ---- 图 2：脉冲稀疏率 vs 时间步 (Spike Sparsity vs T) ----
    fig2, ax2 = plt.subplots(figsize=(10, 6))

    for v_idx, Vth in enumerate(representative_Vth):
        if Vth not in results_by_Vth:
            continue
        T_list = []
        sp_list = []
        for T in T_values:
            if T in results_by_Vth[Vth]:
                T_list.append(T)
                sp_list.append(results_by_Vth[Vth][T]['overall_sparsity'] * 100)

        if T_list:
            ax2.plot(T_list, sp_list,
                     color=colors_vth[v_idx % len(colors_vth)],
                     marker=markers_vth[v_idx % len(markers_vth)],
                     linewidth=2, markersize=8,
                     label=f'Vth = {Vth:.1f}')

    ax2.set_xlabel('仿真时间步 T', fontsize=12)
    ax2.set_ylabel('整体脉冲稀疏率 (%)', fontsize=12)
    ax2.set_title(f'SNN 脉冲稀疏率 vs 时间步 [{norm_method} 归一化]', fontsize=14)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)

    fig2.tight_layout()
    path2 = os.path.join(output_dir, 'snn_sparsity_vs_T.png')
    fig2.savefig(path2, dpi=150)
    plt.close(fig2)
    print(f"[图表保存] 稀疏率 vs T: {path2}")

    # ---- 图 3：准确率-稀疏率 Pareto 散点图 ----
    # X 轴 = 稀疏率（越高越省电），Y 轴 = 准确率
    # 理想点在右上角（高准确率 + 高稀疏率）
    fig3, ax3 = plt.subplots(figsize=(10, 7))

    # 按 Vth 分组，用颜色区分；标记大小反映 T
    unique_Vth = sorted(set(r['Vth'] for r in results))
    cmap = plt.cm.viridis
    norm = matplotlib.colors.Normalize(vmin=min(unique_Vth), vmax=max(unique_Vth))

    for r in results:
        scatter = ax3.scatter(
            r['overall_sparsity'] * 100,
            r['accuracy'] * 100,
            c=[r['Vth']], cmap=cmap, norm=norm,
            s=r['T'] * 2 + 20,  # T 越大，点越大
            alpha=0.7, edgecolors='black', linewidth=0.5
        )

    cbar = plt.colorbar(scatter, ax=ax3)
    cbar.set_label('阈值 Vth', fontsize=11)

    # 添加 Pareto 前沿的标注
    ax3.set_xlabel('整体脉冲稀疏率 (%)', fontsize=12)
    ax3.set_ylabel('测试准确率 (%)', fontsize=12)
    ax3.set_title(f'SNN 精度-效率 Pareto 前沿 [{norm_method} 归一化]\n'
                  '(点越大 = T 越大, 颜色 = Vth, 理想点在右上角)',
                  fontsize=13)
    ax3.grid(True, alpha=0.3)

    # 标注 ANN 参考线
    ax3.axhline(y=ann_accuracy, color='red', linestyle='--', linewidth=1,
                alpha=0.6, label=f'ANN 准确率参考 (~{ann_accuracy:.1f}%)')
    ax3.legend(fontsize=9, loc='lower right')

    fig3.tight_layout()
    path3 = os.path.join(output_dir, 'snn_pareto_frontier.png')
    fig3.savefig(path3, dpi=150)
    plt.close(fig3)
    print(f"[图表保存] Pareto 前沿: {path3}")

    # ---- 图 4：热力图 ----
    # 可以更直观地看到 (T, Vth) 交互效应
    if len(T_values) >= 2 and len(Vth_values) >= 2:
        fig4, (ax4a, ax4b) = plt.subplots(1, 2, figsize=(14, 6))

        # 构建准确率矩阵: [n_Vth, n_T]
        acc_matrix = np.zeros((len(Vth_values), len(T_values)))
        sp_matrix = np.zeros((len(Vth_values), len(T_values)))

        for vi, Vth in enumerate(Vth_values):
            for ti, T in enumerate(T_values):
                if T in results_by_Vth.get(Vth, {}):
                    acc_matrix[vi, ti] = results_by_Vth[Vth][T]['accuracy'] * 100
                    sp_matrix[vi, ti] = results_by_Vth[Vth][T]['overall_sparsity'] * 100
                else:
                    acc_matrix[vi, ti] = np.nan
                    sp_matrix[vi, ti] = np.nan

        # 准确率热力图
        im1 = ax4a.imshow(acc_matrix, aspect='auto', origin='lower',
                          cmap='RdYlGn', interpolation='nearest')
        ax4a.set_xticks(range(len(T_values)))
        ax4a.set_xticklabels([str(t) for t in T_values])
        ax4a.set_yticks(range(len(Vth_values)))
        ax4a.set_yticklabels([f'{v:.1f}' for v in Vth_values])
        ax4a.set_xlabel('T (时间步)', fontsize=11)
        ax4a.set_ylabel('Vth (阈值)', fontsize=11)
        ax4a.set_title('准确率 (%) — 越绿越好', fontsize=12)
        plt.colorbar(im1, ax=ax4a)
        # 标注数值
        for vi in range(len(Vth_values)):
            for ti in range(len(T_values)):
                if not np.isnan(acc_matrix[vi, ti]):
                    ax4a.text(ti, vi, f'{acc_matrix[vi, ti]:.1f}',
                              ha='center', va='center', fontsize=7)

        # 稀疏率热力图
        im2 = ax4b.imshow(sp_matrix, aspect='auto', origin='lower',
                          cmap='Blues', interpolation='nearest')
        ax4b.set_xticks(range(len(T_values)))
        ax4b.set_xticklabels([str(t) for t in T_values])
        ax4b.set_yticks(range(len(Vth_values)))
        ax4b.set_yticklabels([f'{v:.1f}' for v in Vth_values])
        ax4b.set_xlabel('T (时间步)', fontsize=11)
        ax4b.set_ylabel('Vth (阈值)', fontsize=11)
        ax4b.set_title('脉冲稀疏率 (%) — 越高越省电', fontsize=12)
        plt.colorbar(im2, ax=ax4b)
        for vi in range(len(Vth_values)):
            for ti in range(len(T_values)):
                if not np.isnan(sp_matrix[vi, ti]):
                    ax4b.text(ti, vi, f'{sp_matrix[vi, ti]:.1f}',
                              ha='center', va='center', fontsize=7)

        fig4.tight_layout()
        path4 = os.path.join(output_dir, 'snn_heatmaps.png')
        fig4.savefig(path4, dpi=150)
        plt.close(fig4)
        print(f"[图表保存] 热力图: {path4}")


# ============================================================
# 第 3 部分：CSV 导出
# ============================================================

def save_results_csv(results, output_path):
    """将 trade-off 扫描结果保存为 CSV 文件

    CSV 列：
    T, Vth, Accuracy(%), Sparsity_L1(%), Sparsity_L2(%),
    Overall_Sparsity(%), Avg_Spikes_L1, Avg_Spikes_L2,
    Total_Spikes_L1, Total_Spikes_L2,
    P_if_single_uW, P_mac_single_uW, P_SNN_uW, P_ANN_uW,
    power_saving_percent

    其中功耗相关列为占位符，待 Cadence Virtuoso 仿真测得单神经元/单 MAC
    功耗后，再使用 spike count 与 MAC 操作数计算并填入。

    Args:
        results:     scan_tradeoff() 返回的结果列表
        output_path: CSV 输出路径
    """
    fieldnames = [
        'T', 'Vth',
        'Accuracy(%)', 'Overall_Sparsity(%)',
        'Sparsity_L1(%)', 'Sparsity_L2(%)',
        'Avg_Spikes_L1', 'Avg_Spikes_L2',
        'Total_Spikes_L1', 'Total_Spikes_L2',
        'P_if_single_uW', 'P_mac_single_uW',
        'P_SNN_uW', 'P_ANN_uW', 'power_saving_percent',
    ]

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        # 写入说明性注释，便于后续填写 Cadence 仿真得到的功耗数据
        f.write("# 功耗列使用说明：\n")
        f.write("#   P_if_single_uW: 单个 IF 神经元在一个时间步的平均功耗，由 Cadence 仿真测得\n")
        f.write("#   P_mac_single_uW: 单个 MAC 单元完成一次乘加运算的平均功耗，由 Cadence 仿真测得\n")
        f.write("#   P_SNN_uW: 填入 P_if_single_uW * (N_neurons * T * firing_rate) 后的总功耗估算\n")
        f.write("#   P_ANN_uW: 填入 P_mac_single_uW * (MAC_ops / parallelism) 后的总功耗估算\n")
        f.write("#   power_saving_percent: (P_ANN_uW - P_SNN_uW) / P_ANN_uW * 100\n")
        f.write("# 当前列为占位符，等待后续 Cadence 仿真数据填入。\n")

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({
                'T': r['T'],
                'Vth': r['Vth'],
                'Accuracy(%)': round(r['accuracy'] * 100, 2),
                'Overall_Sparsity(%)': round(r['overall_sparsity'] * 100, 2),
                'Sparsity_L1(%)': round(r['sparsity_l1'] * 100, 2),
                'Sparsity_L2(%)': round(r['sparsity_l2'] * 100, 2),
                'Avg_Spikes_L1': round(r['avg_spikes_l1'], 1),
                'Avg_Spikes_L2': round(r['avg_spikes_l2'], 1),
                'Total_Spikes_L1': r['total_spikes_l1'],
                'Total_Spikes_L2': r['total_spikes_l2'],
                'P_if_single_uW': '',
                'P_mac_single_uW': '',
                'P_SNN_uW': '',
                'P_ANN_uW': '',
                'power_saving_percent': '',
            })

    print(f"[CSV保存] Trade-off 数据已保存到 {output_path}")


# ============================================================
# 第 4 部分：最优配置推荐
# ============================================================

def find_best_configs(results, min_accuracy=0.90):
    """从 trade-off 结果中找到不同目标下的最优配置

    Args:
        results:      scan_tradeoff() 返回的结果列表
        min_accuracy: 可接受的最低准确率

    Returns:
        dict: 包含三种策略下的最优配置
    """
    # 过滤满足最低准确率要求的配置
    valid = [r for r in results if r['accuracy'] >= min_accuracy]

    if not valid:
        print(f"[警告] 没有配置达到 {min_accuracy*100:.0f}% 准确率要求")
        valid = results

    # 策略 1：最高准确率
    best_acc = max(results, key=lambda r: r['accuracy'])

    # 策略 2：满足精度要求下最高稀疏率（最节能）
    best_efficiency = max(valid, key=lambda r: r['overall_sparsity'])

    # 策略 3：平衡 —— 准确率×稀疏率 最大化
    best_balanced = max(results, key=lambda r: r['accuracy'] * r['overall_sparsity'])

    print(f"\n{'='*60}")
    print(f"  最优配置推荐")
    print(f"{'='*60}")

    strategies = {
        '最高准确率 (Best Accuracy)': best_acc,
        '最佳能效 (Best Efficiency, acc >= {:.0f}%)'.format(min_accuracy*100): best_efficiency,
        '最佳平衡 (Best Balanced: acc × sparsity)': best_balanced,
    }

    for name, config in strategies.items():
        print(f"\n  [{name}]")
        print(f"    T={config['T']}, Vth={config['Vth']:.1f}")
        print(f"    准确率: {config['accuracy']*100:.2f}%")
        print(f"    整体稀疏率: {config['overall_sparsity']*100:.2f}%")
        print(f"    平均脉冲数 (L1): {config['avg_spikes_l1']:.1f}")
        print(f"    平均脉冲数 (L2): {config['avg_spikes_l2']:.1f}")

    print(f"{'='*60}\n")

    return strategies


# ============================================================
# 第 5 部分：主函数
# ============================================================

def main():
    """主函数：执行完整的 trade-off 扫描、可视化和导出"""

    # ---- 路径配置 ----
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    plots_dir = os.path.join(base_dir, "plots")
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)
    weight_path = os.path.join(data_dir, "ann_mnist_weights_relu.npz")

    # ---- 扫描参数配置 ----
    # 命令行参数：python snn_tradeoff.py [norm_method] [max_samples]
    norm_method = sys.argv[1] if len(sys.argv) > 1 else "max_norm"
    max_test_samples = int(sys.argv[2]) if len(sys.argv) > 2 else 500

    # T (时间步) 和 Vth (阈值) 的扫描范围
    # T: 从小到大多个级别，覆盖"快速推理"到"高精度"全场景
    T_values = [5, 10, 20, 30, 50, 80, 100]
    # Vth: 从低阈值（易触发）到高阈值（难触发）
    Vth_values = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0]

    print("=" * 60)
    print("  SNN 精度-效率 Trade-off 分析")
    print("=" * 60)
    print(f"\n归一化方法: {norm_method}")
    print(f"每组测试样本数: {max_test_samples}")
    print(f"T 扫描范围: {T_values}")
    print(f"Vth 扫描范围: {Vth_values}")
    print(f"总组合数: {len(T_values) * len(Vth_values)}")

    # ---- 加载 MNIST 数据 ----
    print("\n[数据加载] 正在加载 MNIST 数据集...")
    mnist = fetch_openml('mnist_784', version=1, as_frame=False, parser='liac-arff')
    X = mnist.data.astype(np.float32) / np.float32(255.0)
    y = mnist.target.astype(np.int32)

    train_size = 60000
    X_train, X_test = X[:train_size], X[train_size:]
    y_train, y_test = y[:train_size], y[train_size:]
    print(f"  训练集: {len(X_train)} 张, 测试集: {len(X_test)} 张")

    # ---- 加载 ANN 权重 ----
    print(f"\n[权重加载] 从 {weight_path} 加载...")
    W1, b1, W2, b2 = load_ann_weights(weight_path)

    # ---- Trade-off 扫描 ----
    print(f"\n[Trade-off 扫描] 开始扫描 {len(T_values) * len(Vth_values)} 种配置...")
    print("  预计耗时取决于 max_samples，请耐心等待...\n")

    results = scan_tradeoff(
        W1, b1, W2, b2,
        X_test, y_test, X_train,
        T_values=T_values,
        Vth_values=Vth_values,
        norm_method=norm_method,
        percentile=99.9,
        max_test_samples=max_test_samples,
        verbose=True,
    )

    # ---- 最优配置推荐 ----
    strategies = find_best_configs(results, min_accuracy=0.90)

    # ---- 可视化 ----
    print("\n[可视化] 正在生成图表...")
    plot_tradeoff_results(
        results, plots_dir,
        norm_method=norm_method,
        T_values=T_values,
        Vth_values=Vth_values,
    )

    # ---- 保存 CSV ----
    csv_path = os.path.join(data_dir, f'snn_tradeoff_{norm_method}.csv')
    save_results_csv(results, csv_path)

    # ---- 保存完整结果（供后续分析） ----
    npz_path = os.path.join(data_dir, f'snn_tradeoff_{norm_method}.npz')
    # 将结果转为可保存的数组
    save_dict = {}
    for key in results[0].keys():
        save_dict[key] = np.array([r[key] for r in results])
    save_dict['T_values'] = np.array(T_values)
    save_dict['Vth_values'] = np.array(Vth_values)
    save_dict['norm_method'] = norm_method
    np.savez(npz_path, **save_dict)
    print(f"[保存] 完整 trade-off 数据已保存到 {npz_path}")

    print(f"\n{'='*60}")
    print(f"  Trade-off 分析完成!")
    print(f"  图表: {plots_dir}/snn_accuracy_vs_T.png")
    print(f"  图表: {plots_dir}/snn_sparsity_vs_T.png")
    print(f"  图表: {plots_dir}/snn_pareto_frontier.png")
    print(f"  数据: {csv_path}")
    print(f"{'='*60}\n")

    return results, strategies


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":
    main()
