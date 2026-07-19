# 类脑脉冲神经网络与传统人工神经网络的电路实现对比研究

本项目设计并验证了一套基于 Integrate-and-Fire（IF）神经元的脉冲神经网络（SNN）硬件单元，在 MNIST 手写数字识别任务上量化 SNN 相比传统 ANN 的能耗-准确率权衡关系。

## 项目简介

- **硬件平台**：Cadence 180nm 工艺，1.8V 供电
- **核心单元**：
  - MAC 单元：4×4 乘法器 + 4-bit CLA 加法器 + REG4 寄存器
  - IF 神经元：MUX4 积分器 + ADD4 + REG4 + CMP_GE 比较器 + SYNC_RESET
- **网络结构**：MNIST 784 → 300 → 10
- **时钟频率**：2MHz（受 IF 神经元 149ns 关键路径延迟限制）
- **分析方法**：ANN-to-SNN 转换 + (T, Vth) 扫描 + Pareto 前沿分析

## 项目结构

```
.
├── 代码/              # Python 分析脚本与 CSV 数据
│   └── plots/         # 自动生成的 trade-off 图表
├── 报告/              # 报告、网表与测试截图
│   ├── final/         # 结题报告（Markdown + DOCX）
│   ├── figures/       # Testbench 电路图与仿真波形
│   ├── netlists/      # 最终 CDL 网表
│   └── proposal/      # 开题报告相关材料
├── 设计/              # 设计文档与自学材料
└── README.md          # 本文件
```

## 核心结论

| 指标 | ANN（串行单 MAC） | SNN T=50, Vth=0.5 | 对比 |
|---|---|---|---|
| 准确率 | 97.0% | 96.8% | 下降 0.2% |
| 一次推理能量 | 580,000 pJ | 7,634 pJ | SNN 为 ANN 的 1.32% |
| 延迟 @2MHz | 119.1 ms | 25.0 µs | SNN 为 ANN 的 0.021% |
| 节能百分比 | — | 98.68% | — |

- **data_based 归一化显著优于 max_norm**：在相近准确率下，data_based 能耗更低。
- **拐点配置**：T=50, Vth=0.5 是性价比最高点，节能/准确率下降比高达 493.4。
- **SNN 节能来源**：IF 单次事件功耗约为 MAC 的 2 倍，但 SNN 操作数少约 150 倍，系统级能耗仍低两个数量级。

## 主要文件说明

| 文件 | 说明 |
|---|---|
| `代码/report_summary.md` | 结题报告汇总，包含所有测试数据、图表与结论 |
| `代码/ppa_comparison_table.md` | 面积-延迟-功耗综合对比表 |
| `代码/derived_conclusions.md` | 严格基于数据的衍生结论与优化方向 |
| `代码/saving_loss_table.md` | 节能百分比 vs 准确率下降对比表 |
| `代码/fill_power.py` | 用 Cadence 实测功耗填充 CSV |
| `代码/plot_saving_vs_loss.py` | 生成节能-准确率下降核心图 |
| `代码/snn_tradeoff_data_based.csv` | data_based 归一化完整扫描数据 |
| `代码/snn_tradeoff_max_norm.csv` | max_norm 归一化完整扫描数据 |
| `报告/netlists/IF_final.cdl` | 最终 IF 神经元 CDL 网表 |
| `报告/netlists/MAC_final.cdl` | 最终 MAC 单元 CDL 网表 |

## 如何复现

1. **硬件仿真**：在 Cadence Virtuoso 中导入 `报告/netlists/IF_final.cdl` 和 `报告/netlists/MAC_final.cdl`，搭建 Testbench 进行功耗、延迟与功能验证。
2. **数据分析**：
   ```bash
   cd 代码
   python3 fill_power.py              # 填充功耗列
   python3 plot_saving_vs_loss.py     # 生成节能-准确率下降图
   python3 generate_report.py         # 生成汇总报告
   ```

## 数据与测量说明

- **MAC 动态功耗**：4.876 µW（A/B 输入连续翻转，2MHz）
- **IF 动态功耗**：2.627 µW（3 个脉冲事件，2MHz）
- **IF 事件折算因子**：11/3 ≈ 3.67（11 个时钟周期内 3 个有效脉冲事件）
- **晶体管数量**：MAC 942，IF 神经元 514（基于 CDL 自动统计）

## 注意事项与限制

1. ANN 基线采用**单 MAC 串行**模型（parallelism=1），若 ANN 使用更高并行度，SNN 的能耗优势会缩小。
2. 本项目结果基于 **MNIST 784→300→10** 网络，不能直接推广到其他数据集或网络结构。
3. 膜电位为 4-bit，可能存在饱和截断误差；后续可尝试 6-bit 或 8-bit。
4. 当前 IF 神经元无泄漏项，为纯 Integrate-and-Fire 模型。

## 衍生结论（基于数据的节选）

详细分析见 `代码/derived_conclusions.md`。要点：

- **数据直接支持**：data_based 优于 max_norm；T=50 是拐点；IF 延迟限制时钟频率。
- **数据强烈暗示**：存在“零准确率损失”的 SNN 配置（如 max_norm T=100, Vth=5.0），但节能空间会缩小；4-bit 膜电位可能是准确率瓶颈。
- **需谨慎的推测**：LIF 泄漏、SNN-aware 训练、混合 ANN-SNN 架构等需要后续实验验证。

## 许可证

本项目为高中科技创新课题研究使用，代码与设计文件仅供学习交流。
