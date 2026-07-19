* ======================================================
* 运算电路 — 晶体管级 SPICE 网表 (SMIC18MMRF)
* 包含: HA, FA, 4×4 阵列乘法器, 4位 CLA, MAC
*
* 工艺: SMIC 0.18μm CMOS (n18/p18), VDD=1.8V
* ======================================================

.INCLUDE '00_technology.sp'
.INCLUDE '01_basic_gates.sp'


* ======================================================
* 14. 半加器 HA
*
* 逻辑:
*   SUM  = A ⊕ B    (A XOR B)
*   COUT = A · B    (A AND B)
*
* 结构: 1 个 XOR2 + 1 个 AND2
* 晶体管数: 12 + 6 = 18
* ======================================================
.SUBCKT HA A B SUM COUT
XXOR A B SUM XOR2
XAND A B COUT AND2
.ENDS HA


* ======================================================
* 15. 全加器 FA
*
* 逻辑:
*   SUM  = A ⊕ B ⊕ CIN
*   COUT = (A·B) | (CIN·(A⊕B))
*
* 结构: 2 个 XOR2 + 2 个 AND2 + 1 个 OR2
* 晶体管数: 24 + 12 + 6 = 42
* ======================================================
.SUBCKT FA A B CIN SUM COUT
XXOR1 A B XOR_AB XOR2          * XOR_AB = A⊕B
XXOR2 XOR_AB CIN SUM XOR2      * SUM = XOR_AB⊕CIN = A⊕B⊕CIN
XAND1 A B C1 AND2              * C1 = A·B
XAND2 XOR_AB CIN C2 AND2       * C2 = (A⊕B)·CIN
XOR_FA_COUT C1 C2 COUT OR2     * COUT = C1|C2
.ENDS FA


* ======================================================
* 16. 4×4 阵列乘法器 ARRAY_MULT_4X4
*
* 原理: 大学数字电路课程的标准"壁纸式"阵列乘法器
*
* 步骤 1 — 部分积生成:
*   P[i][j] = A[i] · B[j]  (i=0..3, j=0..3)
*   共 16 个 AND2 门
*
* 步骤 2 — 部分积求和 (阵列加法):
*   排列:
*                  P33  P32  P31  P30
*              P23  P22  P21  P20
*          P13  P12  P11  P10
*      P03  P02  P01  P00
*   ─────────────────────────────
*    Y7   Y6   Y5   Y4   Y3   Y2   Y1   Y0
*
*   每一列用 HA/FA 加在一起, 进位传到下一列
*   列 0: Y0 = P00 (最低位)
*   列 1: HA(P01, P10) → Y1, C1
*   列 2: FA(P11, P20, C1) → S2A,C2; HA(S2A, P02) → Y2,C_DUMMY2
*   列 3: FA(P12,P21,C2)+FA(P03,P30,C_DUMMY2)+HA(S3A,S3B)→Y3
*   列 4-6: 类似级联 (P30 加入后每列增加一级)
*
* 晶体管数: 16×AND2 + 4×HA + 8×FA
*          = 96 + 72 + 336 = ~504
* ======================================================
.SUBCKT ARRAY_MULT_4X4 A3 A2 A1 A0 B3 B2 B1 B0 Y7 Y6 Y5 Y4 Y3 Y2 Y1 Y0

* ---- 部分积生成 (16个 AND2 门) ----
XAND00 A0 B0 P00 AND2
XAND01 A0 B1 P01 AND2
XAND02 A0 B2 P02 AND2
XAND03 A0 B3 P03 AND2

XAND10 A1 B0 P10 AND2
XAND11 A1 B1 P11 AND2
XAND12 A1 B2 P12 AND2
XAND13 A1 B3 P13 AND2

XAND20 A2 B0 P20 AND2
XAND21 A2 B1 P21 AND2
XAND22 A2 B2 P22 AND2
XAND23 A2 B3 P23 AND2

XAND30 A3 B0 P30 AND2
XAND31 A3 B1 P31 AND2
XAND32 A3 B2 P32 AND2
XAND33 A3 B3 P33 AND2

* ---- 阵列加法 ----
* 列 0: Y0 = P00
XAND_Y0 P00 VDD Y0 AND2

* 列 1: P01 + P10 = (S1, C1)
XHA_COL1 P01 P10 Y1 C1 HA

* 列 2: P11 + P20 + C1 = (S2, C2); S2 + P02 = Y2
XFA_COL2 P11 P20 C1 S2A C2 FA
XHA_COL2 S2A P02 Y2 C_DUMMY2 HA

* 列 3: P12 + P21 + C2 = S3A_C3A; P03 + P30 + C_DUMMY2 = S3B_C3B; S3A+S3B=Y3_C3C
XFA_COL3A P12 P21 C2 S3A C3A FA
XFA_COL3B P03 P30 C_DUMMY2 S3B C3B FA
XHA_COL3 S3A S3B Y3 C3C HA

* 列 4: P13 + P22 + C3A = S4A_C4A; S4A+P31+C3B=S4B_C4B; S4B+C3C=Y4_C4C
XFA_COL4A P13 P22 C3A S4A C4A FA
XFA_COL4B S4A P31 C3B S4B C4B FA
XHA_COL4 S4B C3C Y4 C4C HA

* 列 5: P23 + P32 + C4A = S5_C5A; S5+C4B+C4C=Y5_C5B
XFA_COL5 P23 P32 C4A S5 C5A FA
XFA_COL5B S5 C4B C4C Y5 C5B FA

* 列 6: P33 + C5A + C5B = Y6_C6
XFA_COL6 P33 C5A C5B Y6 C6 FA

* 列 7: Y7 = 最高位进位
XAND_Y7 C6 VDD Y7 AND2

.ENDS ARRAY_MULT_4X4


* ======================================================
* 17. 4 位超前进位加法器 CLA4
*
* 为什么用 CLA? 行波进位加法器 (如 ADD4) 每级进位都经全加器串联,
* 延迟随位数线性增长. CLA 的进位公式是并行计算的, 延迟≈常数.
*
* 核心公式:
*   产生项 Gi = Ai · Bi
*   传播项 Pi = Ai ⊕ Bi
*
* 进位链 (C0 = CIN):
*   C1 = G0 | (P0 · C0)
*   C2 = G1 | (P1 · G0) | (P1 · P0 · C0)
*   C3 = G2 | (P2 · G1) | (P2 · P1 · G0) | (P2 · P1 · P0 · C0)
*   C4 = G3 | (P3 · G2) | (P3 · P2 · G1) | (P3 · P2 · P1 · G0)
*        | (P3 · P2 · P1 · P0 · C0)
*
* 求和: S[i] = Pi ⊕ Ci
*
* 晶体管数: 8 个 AND2 + 8 个 XOR2 + ~16 个 AND2/OR2 ≈ ~300
* ======================================================
.SUBCKT CLA4 A3 A2 A1 A0 B3 B2 B1 B0 CIN S3 S2 S1 S0 COUT

* ---- 步骤 1: 产生项 Gi, 传播项 Pi ----
XAND_G0 A0 B0 G0 AND2
XAND_G1 A1 B1 G1 AND2
XAND_G2 A2 B2 G2 AND2
XAND_G3 A3 B3 G3 AND2

XXOR_P0 A0 B0 P0 XOR2
XXOR_P1 A1 B1 P1 XOR2
XXOR_P2 A2 B2 P2 XOR2
XXOR_P3 A3 B3 P3 XOR2

* ---- 步骤 2: 超前进位链 ----
* C1 = G0 | (P0 & CIN)
XAND_C1 P0 CIN C1_AND AND2
OR_C1 G0 C1_AND C1 OR2

* C2 = G1 | (P1 & G0) | (P1 & P0 & CIN)
XAND_C2A P1 G0 C2_TERM1 AND2
XAND_C2B P1 P0 C2_TERM2 AND2
XAND_C2C C2_TERM2 CIN C2_TERM3 AND2
OR_C2A G1 C2_TERM1 C2_TMP OR2
OR_C2B C2_TMP C2_TERM3 C2 OR2

* C3 = G2 | (P2 & G1) | (P2 & P1 & G0) | (P2 & P1 & P0 & CIN)
XAND_C3A P2 G1 C3_TERM1 AND2
XAND_C3B P2 P1 C3_TMP1 AND2
XAND_C3C C3_TMP1 G0 C3_TERM2 AND2
XAND_C3D P2 P1 C3_TMP2 AND2
XAND_C3E C3_TMP2 P0 C3_TMP3 AND2
XAND_C3F C3_TMP3 CIN C3_TERM3 AND2
OR_C3A G2 C3_TERM1 C3_TMP4 OR2
OR_C3B C3_TMP4 C3_TERM2 C3_TMP5 OR2
OR_C3C C3_TMP5 C3_TERM3 C3 OR2

* C4 = G3 | (P3 & G2) | (P3 & P2 & G1) | (P3 & P2 & P1 & G0)
*      | (P3 & P2 & P1 & P0 & CIN)
XAND_C4A P3 G2 C4_TERM1 AND2
XAND_C4B P3 P2 C4_TMP1 AND2
XAND_C4C C4_TMP1 G1 C4_TERM2 AND2
XAND_C4D P3 P2 C4_TMP2 AND2
XAND_C4E C4_TMP2 P1 C4_TMP3 AND2
XAND_C4F C4_TMP3 G0 C4_TERM3 AND2
XAND_C4G P3 P2 C4_TMP4 AND2
XAND_C4H C4_TMP4 P1 C4_TMP5 AND2
XAND_C4I C4_TMP5 P0 C4_TMP6 AND2
XAND_C4J C4_TMP6 CIN C4_TERM4 AND2
OR_C4A G3 C4_TERM1 C4_TMP7 OR2
OR_C4B C4_TMP7 C4_TERM2 C4_TMP8 OR2
OR_C4C C4_TMP8 C4_TERM3 C4_TERM5 OR2
OR_C4D C4_TERM5 C4_TERM4 COUT OR2

* ---- 步骤 3: 求和 S[i] = Pi ⊕ Ci ----
XXOR_S0 P0 CIN S0 XOR2
XXOR_S1 P1 C1 S1 XOR2
XXOR_S2 P2 C2 S2 XOR2
XXOR_S3 P3 C3 S3 XOR2

.ENDS CLA4


* ======================================================
* 18. 完整 MAC 单元 (Multiply-Accumulate)
*
* 结构层次:
*   MAC ─┬─ ARRAY_MULT_4X4 (4×4 乘法器, 提供 P=前一时钟周期的
*        │                    乘积)
*        ├─ CLA4 (4位超前进位加法器, 求 P + ACC_prev)
*        ├─ REG4 (4位寄存器, ACC_new→下个周期→ACC_prev)
*        └─ OR2 (进位输出缓冲)
*
* 功能: 每个 CLK↑, ACC <= (A × B) + ACC
*       这就是数字电路中实现"乘累加"的标准架构
*
* 为何用 CLA 而非行波进位加法器?
*   此处 CLA4 加法在关键路径上（乘法结果到来后不能等太久）,
*   行波进位加法器会限制时钟频率.
*
* 晶体管数: ~504 (乘法器) + ~300 (CLA) + ~112 (寄存器) ≈ ~916
* ======================================================
.SUBCKT MAC A3 A2 A1 A0 B3 B2 B1 B0 CLK CLR ACC3 ACC2 ACC1 ACC0 COUT

* 步骤 1: 4×4 乘法 → 8 位乘积 Y[7:0]
XMULT A3 A2 A1 A0 B3 B2 B1 B0 Y7 Y6 Y5 Y4 Y3 Y2 Y1 Y0 ARRAY_MULT_4X4

* 步骤 2: 乘积低4位 + 累加值 → CLA 求新累加值
XCLA Y3 Y2 Y1 Y0 ACC3 ACC2 ACC1 ACC0 0 S3 S2 S1 S0 COUT_INT CLA4

* 步骤 3: 新累加值存入寄存器
XREG S3 S2 S1 S0 CLK CLR ACC3 ACC2 ACC1 ACC0 REG4

* 步骤 4: 进位输出 (OR2 用作缓冲: COUT = COUT_INT OR 0 = COUT_INT)
OR_COUT COUT_INT VSS COUT OR2

.ENDS MAC

* ===== END =====
