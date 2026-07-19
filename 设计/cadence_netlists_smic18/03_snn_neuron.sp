* ======================================================
* SNN-IF 神经元电路 — 晶体管级 SPICE 网表 (SMIC18MMRF)
* 包含: 比较器 A>=B, IF 积分器, 完整 IF 神经元
*
* 工艺: SMIC 0.18μm CMOS (n18/p18), VDD=1.8V
* ======================================================

.INCLUDE '00_technology.sp'
.INCLUDE '01_basic_gates.sp'


* ======================================================
* 19. 4 位比较器 CMP_GE (A >= B)
*
* 功能: 二进制比较器, 判断 A >= B
*
* 逻辑分解 (MSB优先比较):
*   A_GT_B = (A3 & ~B3)                                    [最高位, 权重最大]
*          | (~(A3^B3) & (A2 & ~B2))                       [高位相等, 看次高位]
*          | (~(A3^B3) & ~(A2^B2) & (A1 & ~B1))           [高2位相等, 看第2位]
*          | (~(A3^B3) & ~(A2^B2) & ~(A1^B1) & (A0 & ~B0))[低3位相等, 看最低位]
*
*   A_EQ_B = ~(A3^B3) & ~(A2^B2) & ~(A1^B1) & ~(A0^B0)  [所有位都相等]
*
*   GE = A_GT_B | A_EQ_B
*
* 为什么用这个结构? 这是数字电路中最常用的"逐位比较,
* 一旦分出高低就短路后续比较"的方案, 硬件量最小.
*
* 晶体管数: ~160
* ======================================================
.SUBCKT CMP_GE A3 A2 A1 A0 B3 B2 B1 B0 GE

* ---- 位相等检测: EQ[i] = ~(A[i]⊕B[i]) ----
XXOR_EQ3 A3 B3 X3 XOR2
XINV_EQ3 X3 EQ3 INV

XXOR_EQ2 A2 B2 X2 XOR2
XINV_EQ2 X2 EQ2 INV

XXOR_EQ1 A1 B1 X1 XOR2
XINV_EQ1 X1 EQ1 INV

XXOR_EQ0 A0 B0 X0 XOR2
XINV_EQ0 X0 EQ0 INV

* ---- A>B 逐位比较链 ----
* 位3: A3 > B3 → A3 & ~B3
XINV_B3 B3 B3_N INV
XAND_GT3 A3 B3_N GT3 AND2

* 位2: EQ3 & (A2 & ~B2)
XINV_B2 B2 B2_N INV
XAND_GT2 A2 B2_N GT2_RAW AND2
XAND_GT2F EQ3 GT2_RAW GT2 AND2

* 位1: EQ3 & EQ2 & (A1 & ~B1)
XINV_B1 B1 B1_N INV
XAND_GT1 A1 B1_N GT1_RAW AND2
XAND_EQ32 EQ3 EQ2 EQ32 AND2
XAND_GT1F EQ32 GT1_RAW GT1 AND2

* 位0: EQ3 & EQ2 & EQ1 & (A0 & ~B0)
XINV_B0 B0 B0_N INV
XAND_GT0 A0 B0_N GT0_RAW AND2
XAND_EQ321 EQ32 EQ1 EQ321 AND2
XAND_GT0F EQ321 GT0_RAW GT0 AND2

* 汇总 A>B: GT = GT3 | GT2 | GT1 | GT0
OR_GT_A GT3 GT2 GT_TMP1 OR2
OR_GT_B GT_TMP1 GT1 GT_TMP2 OR2
OR_GT_C GT_TMP2 GT0 A_GT_B OR2

* ---- A=B 检测 ----
XAND_EQ_ALL EQ3 EQ2 EQ_TMP1 AND2
XAND_EQ_A EQ_TMP1 EQ1 EQ_TMP2 AND2
XAND_EQ_B EQ_TMP2 EQ0 A_EQ_B AND2

* ---- GE = A_GT_B | A_EQ_B ----
OR_GE A_GT_B A_EQ_B GE OR2

.ENDS CMP_GE


* ======================================================
* 20. 4 位行波进位加法器 ADD4
*
* 原理: 4 个全加器串联, 每级的进位输出接入下一级的进位输入.
*
* 优点: 结构简单, 晶体管数少
* 缺点: 延迟 = 4 × FA 延迟 (行波进位), 位数多时慢
*
* 晶体管数: 4 × FA ≈ 4 × 42 = 168
* ======================================================
.SUBCKT ADD4 A3 A2 A1 A0 B3 B2 B1 B0 CIN S3 S2 S1 S0 COUT
XFA0 A0 B0 CIN S0 C1 FA
XFA1 A1 B1 C1 S1 C2 FA
XFA2 A2 B2 C2 S2 C3 FA
XFA3 A3 B3 C3 S3 COUT FA
.ENDS ADD4


* ======================================================
* 21. 多路选择器阵列 MUX4 (4位 2选1)
*
* 结构: 4 个 MUX2to1_CORRECT + 4 个 INV (输出缓冲)
* 功能: SEL=0 → Y = D0[3:0]
*       SEL=1 → Y = D1[3:0]
*
* 在 SNN 中的作用:
*   输入脉冲 SPIKE 作为 SEL, 控制突触权重是否通过:
*     SPIKE=0 → Y=0     (无输入脉冲)
*     SPIKE=1 → Y=W[3:0] (输入脉冲到来, 权重注入积分器)
*
* 晶体管数: 4 × 6 + 4 × 2 = 32
* ======================================================
.SUBCKT MUX4 D03 D02 D01 D00 D13 D12 D11 D10 SEL Y3 Y2 Y1 Y0
XMUX0 D00 D10 SEL N0Y MUX2to1_CORRECT
XMUX1 D01 D11 SEL N1Y MUX2to1_CORRECT
XMUX2 D02 D12 SEL N2Y MUX2to1_CORRECT
XMUX3 D03 D13 SEL N3Y MUX2to1_CORRECT
XINV0 N0Y Y0 INV
XINV1 N1Y Y1 INV
XINV2 N2Y Y2 INV
XINV3 N3Y Y3 INV
.ENDS MUX4


* ======================================================
* 22. IF 积分器 (Integrate-and-Fire Integrator)
*
* 这是 SNN 神经元的核心计算单元.
* 它实现的就是代码里的: V += spike * weight
*
* 结构:
*   ┌──────────┐    ┌────────┐    ┌────────┐
*   │   MUX4   │───→│  ADD4  │───→│  REG4  │──→ V[3:0] (膜电位)
*   │ (选通:   │    │ (相加: │    │ (时钟: │
*   │  SPIKE   │    │ V + I) │    │  CLK↑) │
*   │ 控制)    │    │        │    │        │
*   └──────────┘    └────────┘    └──┬─────┘
*                                    │
*                                    └──────────────── V[3:0] 反馈回 ADD4
*
* 工作原理 (每个时间步):
*   1. MUX4: SPIKE=1 → I = W[3:0]; SPIKE=0 → I = 0
*   2. ADD4: 计算 V_new = V_old + I
*   3. REG4: CLK↑ 时存入 V_new
*   4. V_new 回送到 ADD4 输入, 准备下一时间步累加
*
* 晶体管数: MUX4(32) + ADD4(168) + REG4(112) = ~312
* ======================================================
.SUBCKT IF_INTEGRATOR W3 W2 W1 W0 SPIKE CLK CLR V3 V2 V1 V0

* MUX: SPIKE=0 → 选 0; SPIKE=1 → 选权重
* VSS=0 是输入 D0 (选择 0 的那一路)
XWMUX W3 W2 W1 W0 VSS VSS VSS VSS SPIKE I3 I2 I1 I0 MUX4

* 加法: V_new = V_old + I
* V_old 是寄存器反馈回来的
XADD I3 I2 I1 I0 V3 V2 V1 V0 0 S3 S2 S1 S0 COUT_DISCARD ADD4

* 寄存器: CLK↑ 存入新膜电位
XREG S3 S2 S1 S0 CLK CLR V3 V2 V1 V0 REG4

.ENDS IF_INTEGRATOR


* ======================================================
* 23. 完整 IF 神经元 (Integrate-and-Fire Neuron)
*
* 结构:
*   IF_INTEGRATOR ──V[3:0]──→ CMP_GE ──→ SPIKE_OUT
*     (积分器)        (膜电位)  (比较器)   (触发脉冲)
*
* 工作原理 (ANN-to-SNN 映射):
*   Python 代码:                                             硬件实现:
*     V += spike * weight         ──→  MUX(选通) + ADD(累加)
*     if V >= Vth:                ──→  CMP_GE(数字比较)
*         spike_out = 1           ──→  GE 输出高电平
*         V = 0                   ──→  CLR 清零 (下一 CLK↑)
*
* 晶体管数: ~312 + ~160 = ~472
* ======================================================
.SUBCKT IF_NEURON W3 W2 W1 W0 SPIKE CLK CLR VTH3 VTH2 VTH1 VTH0 V3 V2 V1 V0 SPIKE_OUT

* 积分器
XINTEG W3 W2 W1 W0 SPIKE CLK CLR V3 V2 V1 V0 IF_INTEGRATOR

* 比较器: V >= Vth? → SPIKE (CMP_GE 的 GE 是正逻辑: A>=B→1, 直接输出)
XCMP V3 V2 V1 V0 VTH3 VTH2 VTH1 VTH0 SPIKE_OUT CMP_GE

.ENDS IF_NEURON


* ======================================================
* 24. 同步复位脉冲整形器 SYNC_RESET
*
* 作用: 当 IF 神经元触发脉冲 (SPIKE_RAW=1) 时,
*       产生一个延迟一拍的清零信号.
*       这样膜电位在触发脉冲输出的下一个 CLK↑ 才清零,
*       保证脉冲输出有完整的时钟宽度供后续电路采样.
*
* 结构: 1 个 DFF
*         D=SPIKE_RAW, CLK=CLK, Q=CLR_SYNC
*
* 时序图:
*   CLK        ___↑_______↑_______↑_______
*   SPIKE_RAW  ______|‾‾‾‾‾‾‾|___________
*   CLR_SYNC   ____________|‾‾‾‾|_______
*   膜电位 V   ████----████----0000----
*                                   ↑
*                         这里才清零, SPIKE_RAW 已输出一个完整周期
*
* 晶体管数: 1 × DFF = 24
* ======================================================
.SUBCKT SYNC_RESET SPIKE_RAW CLK CLR_SYNC
XDFF_SYNC SPIKE_RAW CLK CLR_SYNC CLR_SYNC_N DFF
.ENDS SYNC_RESET


* ======================================================
* 25. 完整 IF 神经元 (带同步复位) IF_NEURON_FULL
*
* 组合: IF_INTEGRATOR + CMP_GE + SYNC_RESET
*
* 完整时序周期:
*   T0: V = 0 (初始态)
*   T1: SPIKE=1 → V = W (第一次积分)
*   T2: SPIKE=1 → V = 2W (第二次积分)
*   T3: V >= Vth? → SPIKE_RAW=1; 同时 V 继续累加
*   T4: SPIKE_RAW 经 DFF → CLR_SYNC 上升
*   T5: CLR_SYNC → REG4 清零 → V=0
*   然后回到 T1 继续
*
* 晶体管数: ~472 + 24 = ~496
* ======================================================
.SUBCKT IF_NEURON_FULL W3 W2 W1 W0 SPIKE_IN CLK CLR VTH3 VTH2 VTH1 VTH0 V3 V2 V1 V0 SPIKE_OUT

* 比较器输出 (组合逻辑, 立即响应, 正逻辑: V>=Vth→1)
XCMP V3 V2 V1 V0 VTH3 VTH2 VTH1 VTH0 SPIKE_RAW CMP_GE

* 同步复位生成 (SPIKE_RAW 触发 → 下一拍 CLR_SYNC 有效)
XSYNC SPIKE_RAW CLK CLR_SYNC SYNC_RESET

* 外部与同步复位组合
OR_CLR CLR CLR_SYNC CLR_COMB OR2

* 积分器 (带组合复位)
XINTEG W3 W2 W1 W0 SPIKE_IN CLK CLR_COMB V3 V2 V1 V0 IF_INTEGRATOR

* 脉冲输出缓冲 (正逻辑, 无需反相)
OR_SPK_OUT SPIKE_RAW VSS SPIKE_OUT OR2

.ENDS IF_NEURON_FULL

* ===== END =====
