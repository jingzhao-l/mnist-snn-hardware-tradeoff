# SMIC18MMRF 版 Cadence Virtuoso 电路网表使用指南

**工艺: SMIC 0.18μm CMOS (n18/p18), VDD=1.8V**

## 文件清单

| 文件 | 内容 | 晶体管数 |
|------|------|---------|
| `00_technology.sp` | 工艺设定 (器件: n18/p18, VDD=1.8V) | — |
| `01_basic_gates.sp` | INV→NAND2→AND2→NOR2→OR2→TG→XOR2→MUX2to1→DFF→REG4 | 2~112 |
| `02_arithmetic.sp` | HA→FA→4×4阵列乘法器→CLA4→MAC | 12~800 |
| `03_snn_neuron.sp` | CMP_GE→ADD4→MUX4→IF_INTEGRATOR→IF_NEURON_FULL | 120~488 |
| `testbench_mac.sp` | MAC 功能验证 (A=3×B=5 累加) | — |
| `testbench_snn.sp` | SNN-IF 功能验证 (W=2, Vth=3) | — |

## 如何在 Virtuoso Schematic Editor 中使用

### 方式一: SPICE → Schematic 自动导入 (推荐)

1. 打开 Virtuoso CIW (Command Interpreter Window)
2. `File → Import → SPICE`
3. 设置:
   - **Input File**: 选择 `01_basic_gates.sp`
   - **Output Library**: 点击 New Library → 命名 `MY_SNN` → 选 `smic18mmrf` attach
   - **Output View Name**: `schematic`
4. OK → 自动为 13 个 `.SUBCKT` 生成原理图
5. 重复导入 `02_arithmetic.sp`, `03_snn_neuron.sp`

⚠️ **注意**: 自动生成的原理图晶体管摆位较乱，建议右键自动排列 (Edit → Hierarchy → Check and Save 后手动整理)。但连接关系完全正确，可以直接仿真。

### 方式二: 从底层手动画

如果你老师希望你自己画, 可以按这个顺序搭:

```
1. 先画 INV (1 PMOS + 1 NMOS, 确认能正常工作)
2. NAND2, NOR2 (理解串并联的区别)
3. AND2 = NAND2 + INV, OR2 = NOR2 + INV
4. TG (传输门, 理解 NMOS/PMOS 互补导通)
5. XOR2 (用 TG 搭)
6. MUX2to1 (2个TG + 1个INV)
7. DFF (4个TG + 4个INV = 主从锁存)
8. DFF_CLR (DFF + AND2)
9. REG4 = DFF_CLR × 4
10. HA = XOR2 + AND2
11. FA = 2×XOR2 + 2×AND2 + OR2
12. ARRAY_MULT_4X4 (结构复杂, 但全部由 HA/FA/AND2 组成)
13. CLA4 (超前进位链, 全是 AND2/XOR2/OR2)
14. MAC = MULT + CLA + REG
15. CMP_GE (全是 XOR2/AND2/OR2)
16. IF_INTEGRATOR = MUX4 + ADD4 + REG4
17. IF_NEURON_FULL = IF_INTEGRATOR + CMP_GE + SYNC_RESET
```

关键提示: **画图时复制已有的 cell 作为 instance 放入上层, 不要每个晶体管都自己画**, 否则 MAC 要画 800 个管。

## SMIC18MMRF 晶体管参数

| 参数 | 值 |
|------|-----|
| NMOS 器件名 | `n18` |
| PMOS 器件名 | `p18` |
| NMOS 宽度 | 0.5μm |
| PMOS 宽度 | 1.0μm (2×NMOS 以匹配驱动) |
| 沟道长度 | 0.18μm (最小) |
| VDD | 1.8V |
| NMOS 阈值 | ~0.45V |
| PMOS 阈值 | ~-0.45V |

## 两种加法器的区别

在网表中给出了两种 4 位加法器, 理解它们的区别:

| | ADD4 (行波进位) | CLA4 (超前进位) |
|---|---|---|
| 结构 | 4个FA串联 | 并行进位逻辑 |
| 延迟 | 4×FA延迟 ⬆ 线性增长 | ~2-3门延迟 ⬆ 常数 |
| 晶体管 | ~120 | ~300 |
| 用在 | SNN 积分器 (时序不紧) | MAC 关键路径 |

## 阈值 Vth 是什么

SNN 的 IF_NEURON 中, Vth 是**数字信号** (4位二进制数), 设定为 3 (0011) 意味着膜电位达到 3 以上就触发。

但在实际 AI 芯片中, Vth 是**模拟电压信号** (如 1.0V 电压)。我们这里简化为数字比较, 因为 4 位的精度已经能演示完整的 ANN-to-SNN 映射原理。
