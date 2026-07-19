#!/usr/bin/env python3
"""
generate_report.py — 生成本项目的结题报告汇总
===============================================
读取两个 trade-off CSV，提取 Pareto 前沿，生成：
  1. report_summary.md — 可直接写入论文/结题报告的中文汇总
  2. pareto_summary.csv — Pareto 配置表
  3. snn_tradeoff_comparison.png — data_based 与 max_norm 同图对比
"""

import csv
import os

import fill_power as fp
import count_transistors as ct
import matplotlib
matplotlib.use('Agg')
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np


def set_chinese_font():
    """设置中文字体，避免图表乱码。"""
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


def write_pareto_csv(pareto_data, output_path):
    """保存 Pareto 配置到 CSV。"""
    fieldnames = [
        'method', 'T', 'Vth', 'Accuracy(%)', 'Overall_Sparsity(%)',
        'P_SNN_uW', 'P_ANN_uW', 'power_saving_percent', 'SNN/ANN(%)'
    ]
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for method, rows in pareto_data.items():
            for r in rows:
                writer.writerow({
                    'method': method,
                    'T': int(r['T']),
                    'Vth': r['Vth'],
                    'Accuracy(%)': r['Accuracy(%)'],
                    'Overall_Sparsity(%)': r['Overall_Sparsity(%)'],
                    'P_SNN_uW': round(r['P_SNN_uW'], 3),
                    'P_ANN_uW': round(r['P_ANN_uW'], 3),
                    'power_saving_percent': round(r['power_saving_percent'], 2),
                    'SNN/ANN(%)': round(100 * r['P_SNN_uW'] / r['P_ANN_uW'], 3),
                })
    print(f'[CSV 保存] {output_path}')


def plot_comparison(data_based, max_norm, output_path):
    """data_based 与 max_norm 的 Pareto 前沿同图对比。"""
    pareto_db = get_pareto(data_based)
    pareto_mn = get_pareto(max_norm)

    fig, ax = plt.subplots(figsize=(10, 7))

    ax.plot(
        [100 * r['P_SNN_uW'] / r['P_ANN_uW'] for r in pareto_db],
        [r['Accuracy(%)'] for r in pareto_db],
        'b-o', linewidth=2.5, markersize=8, label='data_based 归一化'
    )
    ax.plot(
        [100 * r['P_SNN_uW'] / r['P_ANN_uW'] for r in pareto_mn],
        [r['Accuracy(%)'] for r in pareto_mn],
        'g-s', linewidth=2.5, markersize=8, label='max_norm 归一化'
    )

    ax.axhline(97.0, color='gray', linestyle=':', linewidth=1.2,
               label='ANN 参考准确率 ~97%')
    ax.axvline(100.0, color='gray', linestyle=':', linewidth=1.2,
               label='SNN 能耗 = ANN 能耗')

    ax.set_xscale('log')
    ax.set_xlabel('SNN 能耗 / ANN 能耗 (%) — 越小越省电', fontsize=12)
    ax.set_ylabel('测试准确率 (%)', fontsize=12)
    ax.set_title('data_based 与 max_norm 的 SNN 能耗-准确率 Pareto 前沿对比',
                 fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, which='both')

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f'[图表保存] {output_path}')


def markdown_table(rows):
    """把 Pareto 配置列表转成 Markdown 表格字符串。"""
    lines = []
    lines.append(
        '| T | Vth | 准确率(%) | 整体稀疏率(%) | SNN能耗(mW·cycle) | '
        '节能(%) | SNN/ANN(%) |'
    )
    lines.append(
        '|---|---|---|---|---|---|---|'
    )
    for r in rows:
        lines.append(
            f"| {int(r['T'])} | {r['Vth']:.2f} | {r['Accuracy(%)']:.1f} | "
            f"{r['Overall_Sparsity(%)']:.2f} | {r['P_SNN_uW']/1e3:.3f} | "
            f"{r['power_saving_percent']:.2f} | "
            f"{100*r['P_SNN_uW']/r['P_ANN_uW']:.3f} |"
        )
    return '\n'.join(lines)


def correction_comparison_table(rows, p_if_corrected, p_if_uncorrected):
    """生成 IF 折算前后对比的 Markdown 表格（取 Pareto 前沿）。"""
    pareto = get_pareto(rows)
    ratio = p_if_uncorrected / p_if_corrected
    lines = []
    lines.append(
        '| T | Vth | 折算后 P_SNN(mW·cycle) | 折算后节能(%) | '
        '未折算 P_SNN(mW·cycle) | 未折算节能(%) |'
    )
    lines.append('|---|---|---|---|---|---|')
    for r in pareto:
        p_snn_corr = r['P_SNN_uW']
        p_snn_unc = p_snn_corr * ratio
        saving_corr = r['power_saving_percent']
        p_ann = r['P_ANN_uW']
        saving_unc = (p_ann - p_snn_unc) / p_ann * 100.0
        lines.append(
            f"| {int(r['T'])} | {r['Vth']:.2f} | {p_snn_corr/1e3:.3f} | "
            f"{saving_corr:.2f} | {p_snn_unc/1e3:.3f} | {saving_unc:.2f} |"
        )
    return '\n'.join(lines)


def write_report(data_based, max_norm, output_path):
    """生成中文 Markdown 汇总报告。"""
    pareto_db = get_pareto(data_based)
    pareto_mn = get_pareto(max_norm)

    best_db = max(data_based, key=lambda r: r['Accuracy(%)'])
    best_mn = max(max_norm, key=lambda r: r['Accuracy(%)'])

    p_if_corrected = fp.P_IF_SINGLE_UW
    p_if_uncorrected = fp.P_IF_DYNAMIC_UW - fp.P_IF_STATIC_UW
    p_mac_single = fp.P_MAC_SINGLE_UW
    mac_ops = fp.MAC_OPS
    p_ann_ref = p_mac_single * mac_ops

    # 从最终 CDL 计算晶体管数量
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if_path = os.path.join(base_dir, '..', '报告', 'netlists', 'IF_final.cdl')
    mac_path = os.path.join(base_dir, '..', '报告', 'netlists', 'MAC_final.cdl')

    def get_transistor_count(path):
        if os.path.exists(path):
            subs, top = ct.parse_cdl(path)
            return ct.count_transistors(subs, top), top
        return 0, 'N/A'

    if_count, if_top = get_transistor_count(if_path)
    mac_count, mac_top = get_transistor_count(mac_path)

    # 单次操作能量（µW / MHz = pJ）
    e_mac_pj = p_mac_single / fp.F_CLK_MHZ
    e_if_pj = p_if_corrected / fp.F_CLK_MHZ

    # 选取两个 data_based 推荐配置做系统级对比
    r_db_50 = next(r for r in data_based if r['T'] == 50 and r['Vth'] == 0.5)
    r_db_20 = next(r for r in data_based if r['T'] == 20 and r['Vth'] == 0.75)

    content = f"""# SNN-ANN 能耗-准确率权衡分析 — 结题报告汇总

## 一、项目目标

本课题设计并验证了一套基于 **Integrate-and-Fire (IF) 神经元** 的脉冲神经网络硬件单元，
包括：
- **MAC 单元**：4×4 乘法器 + 4-bit CLA 加法器 + REG4 寄存器
- **IF 神经元**：MUX4 积分器 + ADD4 + REG4 + CMP_GE 比较器 + SYNC_RESET

核心问题：在 MNIST 手写数字识别任务上，量化 **SNN 相比 ANN 每节省多少功耗，会损失多少准确率**。

---

## 二、硬件电路验证结果

| 模块 | 关键修复 | 验证结论 |
|---|---|---|
| DFF | 修正 Q=~D 的反相问题，确认下降沿触发 | Q=D，CLR 高电平有效 |
| MAC | 确认 4-bit 截断设计，DFF 反相修复 | A=5,B=5 累加序列正确：0→9→2→11→4→13→6… |
| IF 神经元 | MUX4 选择逻辑修正：SPIKE=1 时选 W | V 正确累加 0→2→4→6，SPIKE_OUT 按时触发 |

---

## 二、测试平台与功能验证波形

### 2.1 测试平台电路图

IF 神经元功耗/功能测试平台：

![IF testbench](../报告/figures/IF_TB.png)

MAC 单元功耗/功能测试平台：

![MAC testbench](../报告/figures/MAC_TB.png)

### 2.2 功耗测试波形

IF 神经元在 2MHz 下的功耗测试波形（W=0010, Vth=0110，3 个 SPIKE_IN 脉冲）：

![IF 2MHz 波形](../报告/figures/IF（2MHz）波形图.png)

MAC 单元在 2MHz 下的功耗测试波形（A/B 输入翻转）：

![MAC 2MHz 波形](../报告/figures/MAC（2MHz）波形图.png)

### 2.3 功能验证记录

#### DFF

| 验证项 | 预期 | 实测 | 结论 |
|---|---|---|---|
| 触发边沿 | 下降沿触发 | 下降沿触发 | 通过 |
| Q 与 D 关系 | Q = D | Q = D | 通过 |
| CLR 复位 | CLR 高电平时复位 | 0–600 ns 复位有效 | 通过 |

#### MAC 单元

| 编号 | 输入 A | 输入 B | 乘积低 4 位 | 预期 ACC 序列 | 实测结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 0000 (0) | 0000 (0) | 0 | 保持 0 | ACC = 0 | 通过 |
| 2 | 0001 (1) | 0000 (0) | 0 | 保持 0 | ACC = 0 | 通过 |
| 3 | 0000 (0) | 0001 (1) | 0 | 保持 0 | ACC = 0 | 通过 |
| 4 | 0001 (1) | 0001 (1) | 1 | 0 → 1 → 2 → 3 … | 每个周期 +1 | 通过 |
| 5 | 0101 (5) | 0101 (5) | 9 | 0 → 9 → 2 → 11 → 4 → 13 → 6 … | 与序列一致 | 通过 |

#### IF 神经元

| 编号 | W | Vth | SPIKE_IN | 预期膜电位 V 序列 | 实测结果 | 结论 |
|---|---|---|---|---|---|---|
| 1 | 0010 (2) | 0110 (6) | 3 个脉冲 | 0 → 2 → 4 → 6 → 0 | V 正确累加，达到阈值后复位 | 通过 |

---

## 三、Cadence 实测功耗、延迟与晶体管数

### 3.1 测试参数记录

#### MAC 功耗 testbench

| 参数 | 数值 | 说明 |
|---|---|---|
| CLK period | 500 ns | 2MHz |
| CLK width | 250 ns | 50% 占空比 |
| CLR width | 600 ns | 0–600 ns 高电平复位 |
| A0–A3 | vpulse 二进制计数 | 周期 1u/2u/4u/8u，A 从 0→15 循环 |
| B0–B3 | vpulse 二进制计数（相位错开） | 周期 1u/2u/4u/8u，与 A 不同相 |
| Stop Time | 16 µs | 共 32 个时钟周期 |
| VDD | 1.8 V | 独立 vdc 接 VDD! 与 gnd! |

MAC 每个时钟周期完成一次乘累加，因此**无需额外事件折算**（折算因子 = 1.0），
测得的平均功耗直接作为单次 MAC 运算功耗。

#### IF 神经元功耗 testbench

| 参数 | 数值 | 说明 |
|---|---|---|
| CLK period | 500 ns | 2MHz，下降沿触发 |
| CLK width | 250 ns | 50% 占空比 |
| CLR width | 600 ns | 0–600 ns 高电平复位 |
| W | 0010 | 权重为 2 |
| Vth | 0110 | 阈值为 6 |
| SPIKE_IN 脉冲 1 | 1.1 µs – 1.4 µs | 宽 300 ns |
| SPIKE_IN 脉冲 2 | 2.6 µs – 2.9 µs | 宽 300 ns |
| SPIKE_IN 脉冲 3 | 4.1 µs – 4.4 µs | 宽 300 ns |
| Stop Time | 5.5 µs | 共 11 个时钟周期，3 个有效脉冲事件 |
| VDD | 1.8 V | 独立 vdc 接 VDD! 与 gnd! |

### 3.2 测量结果

| 指标 | MAC 单元 | IF 神经元 | 备注 |
|---|---|---|---|
| 动态功耗 | {fp.P_MAC_DYNAMIC_UW:.3f} µW | {fp.P_IF_DYNAMIC_UW:.3f} µW | 2MHz，1.8V |
| 静态功耗 | {fp.P_MAC_STATIC_UW:.6f} µW | {fp.P_IF_STATIC_UW:.6f} µW | 输入全 1，CLK=0，CLR=0 |
| 未折算有效功耗 | {p_mac_single:.3f} µW | {p_if_uncorrected:.3f} µW | 动态 - 静态 |
| 折算后有效功耗 | {p_mac_single:.3f} µW | {p_if_corrected:.3f} µW | 未折算 × {fp.IF_EVENT_CORRECTION_FACTOR:.2f} |
| 关键路径延迟 | ~50 ns | ~149 ns | 2MHz 时钟下满足时序 |
| 晶体管数量 | {mac_count} | {if_count} | 基于 {mac_top} / {if_top} 最终 CDL |
| 单次操作能量 | {e_mac_pj:.3f} pJ | {e_if_pj:.3f} pJ | @ {fp.F_CLK_MHZ:.0f}MHz |

> **折算说明**：IF 测试窗口 5.5 µs 内只有 3 个有效脉冲事件，因此把测得的平均功耗按
> `11 / 3 ≈ {fp.IF_EVENT_CORRECTION_FACTOR:.2f}` 放大，得到“每次脉冲事件”的等效功耗。

### 3.3 面积-延迟-功耗综合对比

#### 单元级对比

| 指标 | MAC 单元 | IF 神经元 | IF / MAC 比值 |
|---|---|---|---|
| 晶体管数量（面积 proxy） | {mac_count} | {if_count} | {if_count/mac_count:.3f} |
| 关键路径延迟 | ~50 ns | ~149 ns | {149/50:.2f} |
| 动态功耗（测试台平均） | {fp.P_MAC_DYNAMIC_UW:.3f} µW | {fp.P_IF_DYNAMIC_UW:.3f} µW | {fp.P_IF_DYNAMIC_UW/fp.P_MAC_DYNAMIC_UW:.3f} |
| 有效单次功耗 | {p_mac_single:.3f} µW | {p_if_corrected:.3f} µW | {p_if_corrected/p_mac_single:.3f} |
| 单次操作能量 | {e_mac_pj:.3f} pJ | {e_if_pj:.3f} pJ | {e_if_pj/e_mac_pj:.3f} |

#### 系统级对比（data_based 推荐配置）

| 系统 | 准确率 | 一次推理能耗 | 相对 ANN 能耗 | 推理周期数 | 延迟 @2MHz | 相对 ANN 延迟 |
|---|---|---|---|---|---|---|
| ANN（串行单 MAC） | 97.0% | {p_ann_ref/1e3:.2f} mW·cycle | 100% | {mac_ops:,} | {mac_ops/fp.F_CLK_MHZ/1e3:.1f} ms | 100% |
| SNN T=50, Vth=0.5 | {r_db_50['Accuracy(%)']:.1f}% | {r_db_50['P_SNN_uW']/1e3:.3f} mW·cycle | {100*r_db_50['P_SNN_uW']/r_db_50['P_ANN_uW']:.2f}% | 50 | 25.0 µs | {50/mac_ops*100:.4f}% |
| SNN T=20, Vth=0.75 | {r_db_20['Accuracy(%)']:.1f}% | {r_db_20['P_SNN_uW']/1e3:.3f} mW·cycle | {100*r_db_20['P_SNN_uW']/r_db_20['P_ANN_uW']:.2f}% | 20 | 10.0 µs | {20/mac_ops*100:.4f}% |

> 说明：此处 ANN 采用单 MAC 串行基线（parallelism=1）。若 ANN 使用更多 MAC 并行，其延迟会下降，但单位面积功耗会同比上升；本表用于说明 SNN 在事件稀疏性上的数量级优势。

---

## 四、ANN 参考能耗

网络结构：784 → 300 → 10

```text
总 MAC 次数 = 784×300 + 300×10 = 238,200
ANN 能耗    = {p_mac_single:.3f} µW × 238,200 = {p_ann_ref/1e3:.2f} mW·cycle
ANN 准确率  ≈ 97.0%
```

---

## 五、SNN 推荐配置（Pareto 前沿）

### 5.1 data_based 归一化（推荐）

{markdown_table(pareto_db)}

**最高准确率配置**：T={int(best_db['T'])}, Vth={best_db['Vth']:.2f}，
准确率 {best_db['Accuracy(%)']:.1f}%，SNN 能耗为 ANN 的
{100*best_db['P_SNN_uW']/best_db['P_ANN_uW']:.2f}%。

### 5.2 max_norm 归一化

{markdown_table(pareto_mn)}

**最高准确率配置**：T={int(best_mn['T'])}, Vth={best_mn['Vth']:.2f}，
准确率 {best_mn['Accuracy(%)']:.1f}%，SNN 能耗为 ANN 的
{100*best_mn['P_SNN_uW']/best_mn['P_ANN_uW']:.2f}%。

---

## 六、IF 功耗折算前后对比

下表展示 **data_based** 方法下，IF 功耗按实际脉冲事件折算前后的 Pareto 结果差异：

{correction_comparison_table(data_based, p_if_corrected, p_if_uncorrected)}

> 说明：未折算时，把 IF 测试窗口内的平均功耗直接当成“每次事件功耗”，会显著高估 SNN 的节能效果；
> 折算后更贴近事件驱动的真实能耗。

---

## 七、核心结论

1. **data_based 归一化显著优于 max_norm**：在相近准确率下，data_based 的 SNN 能耗更低。
2. **SNN 节能来自事件稀疏性**：即使单次 IF 事件功耗高于单次 MAC，SNN 一次推理的脉冲事件数
   （约 1,000–7,000）远少于 ANN 的 MAC 次数（238,200），因此总量上仍节能 94%–99%。
3. **“节能百分比 vs 准确率下降”曲线存在明显拐点（knee point）**：
   - 从 ANN 切换到 SNN（T=50, Vth=0.5）时，准确率仅下降约 0.2%，即可节能 98.68%，
     这是**性价比最高的区域**。
   - 继续压缩到 T=5 虽然能把节能推到 99.92%，但准确率会再下降约 4.8%，
     属于“为最后一点节能付出过大准确率代价”的区域。
   - 因此，本课题的实用甜点（sweet spot）在 **T=20~50、Vth=0.5~1.5** 之间。
4. **归一化方法对 trade-off 影响巨大**：
   - max_norm 在 T=5、Vth=5.0 时准确率会跌至 12.4%，几乎不可用；
   - 而 data_based 在相近节能水平下仍能保持 92.2% 的准确率。
   - 这说明 **“按数据分布缩放权重”是 SNN 转换成功的关键**。
5. **推荐硬件部署点**（基于全部 Pareto 前沿数据）：
   - 若追求最高准确率：data_based, T={int(best_db['T'])}, Vth={best_db['Vth']:.2f}，准确率 {best_db['Accuracy(%)']:.1f}%，SNN 能耗为 ANN 的 {100*best_db['P_SNN_uW']/best_db['P_ANN_uW']:.2f}%，节能 {best_db['power_saving_percent']:.2f}%。
   - 若追求最大节能：data_based, T=5, Vth=0.5，准确率 92.2%，SNN 能耗为 ANN 的 0.08%，节能 99.92%。
   - max_norm 最高准确率：T={int(best_mn['T'])}, Vth={best_mn['Vth']:.2f}，准确率 {best_mn['Accuracy(%)']:.1f}%，SNN 能耗为 ANN 的 {100*best_mn['P_SNN_uW']/best_mn['P_ANN_uW']:.2f}%，节能 {best_mn['power_saving_percent']:.2f}%。
6. **时钟频率必须降至 2MHz**：IF 神经元关键路径延迟约 149 ns，超过 10MHz 的 100 ns 周期。
7. **结论基于全部 (T, Vth) 扫描数据**：完整数据表见 `full_results_table.md`，核心曲线见
   `plots/snn_saving_vs_loss_data_based.png`，Pareto 前沿从所有 49 组 data_based 和 49 组 max_norm 配置中计算得出。

---

## 八、关键文件清单

| 文件 | 说明 |
|---|---|
| `snn_conversion.py` | ANN-to-SNN 转换与 IF 神经元仿真 |
| `snn_tradeoff.py` | (T, Vth) 扫描与 CSV/图表生成 |
| `fill_power.py` | 用 Cadence 实测功耗填充 CSV |
| `plot_power_tradeoff.py` | 功耗-准确率 trade-off 可视化 |
| `count_transistors.py` | 自动统计 CDL 晶体管数量 |
| `generate_report.py` | 生成本报告 |
| `snn_tradeoff_data_based.csv` | data_based 完整数据 |
| `snn_tradeoff_max_norm.csv` | max_norm 完整数据 |
| `full_results_table.md` | 全部 (T, Vth) 配置汇总表 |
| `plots/*.png` | 全部 trade-off 图表 |

---

*报告生成时间：2026-07-18*
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'[报告保存] {output_path}')


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_based_path = os.path.join(base_dir, 'snn_tradeoff_data_based.csv')
    max_norm_path = os.path.join(base_dir, 'snn_tradeoff_max_norm.csv')

    data_based = read_csv(data_based_path)
    max_norm = read_csv(max_norm_path)

    output_csv = os.path.join(base_dir, 'pareto_summary.csv')
    output_md = os.path.join(base_dir, 'report_summary.md')
    output_png = os.path.join(base_dir, 'plots', 'snn_tradeoff_comparison.png')

    pareto_data = {'data_based': get_pareto(data_based),
                   'max_norm': get_pareto(max_norm)}

    write_pareto_csv(pareto_data, output_csv)
    plot_comparison(data_based, max_norm, output_png)
    write_report(data_based, max_norm, output_md)

    print('\n[完成] 报告、Pareto CSV、对比图已生成。')


if __name__ == '__main__':
    main()
