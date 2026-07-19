* ======================================================
* 基本门电路 — 晶体管级 SPICE 网表 (SMIC18MMRF)
*
* 工艺: SMIC 0.18μm CMOS (n18/p18)
* VDD: 1.8V
* 默认尺寸: NMOS W=0.5μm, PMOS W=1.0μm, L=0.18μm
* ======================================================

.INCLUDE '00_technology.sp'


* ======================================================
* 1. 反相器 INV
*
* 原理图:
*         VDD
*          │
*       ┌──┘
*       │ MP1 (p18)
*       │   栅极=IN, 源=VDD, 漏=OUT
*    IN─┤
*       │ MN1 (n18)
*       │   栅极=IN, 源=VSS, 漏=OUT
*       └──┐
*          │
*         VSS
*
* 真值表: IN=0 → MN1关 MP1开 → OUT=VDD=1
*         IN=1 → MN1开 MP1关 → OUT=VSS=0
*
* 晶体管数: 2
* ======================================================
.SUBCKT INV IN OUT
MN1 OUT IN VSS VSS n18 W={W_N} L={L_MIN}
MP1 OUT IN VDD VDD p18 W={W_P} L={L_MIN}
.ENDS INV


* ======================================================
* 2. 与非门 NAND2
*
* 原理图:
*         VDD
*          │
*       MP2──MP1 (p18, 并联)
*       A─┤  B─┤    任一输入为0, 对应PMOS导通, OUT=1
*          │
*          ├─── OUT
*          │
*       MN1──MN2 (n18, 串联)
*       A─┤  B─┤    两个输入都为1, 两个NMOS都导通, OUT=0
*          │
*         VSS
*
* 注意: NMOS 串联宽度加倍 = W_N*2
*
* 真值表: NAND(A,B) = NOT(A AND B)
*   A B | OUT
*   0 0 | 1
*   0 1 | 1
*   1 0 | 1
*   1 1 | 0
*
* 晶体管数: 4
* ======================================================
.SUBCKT NAND2 A B OUT
MN1 OUT A N1 VSS n18 W={W_N*2} L={L_MIN}
MN2 N1 B VSS VSS n18 W={W_N*2} L={L_MIN}
MP1 OUT A VDD VDD p18 W={W_P} L={L_MIN}
MP2 OUT B VDD VDD p18 W={W_P} L={L_MIN}
.ENDS NAND2


* ======================================================
* 3. 与门 AND2 = NAND2 + INV
*
* 晶体管数: 6
* ======================================================
.SUBCKT AND2 A B OUT
XNAND A B NAND_OUT NAND2
XINV NAND_OUT OUT INV
.ENDS AND2


* ======================================================
* 4. 或非门 NOR2
*
* 原理图:
*         VDD
*          │
*       MP1──MP2 (p18, 串联)
*       A─┤  B─┤    两个输入都为0, 两个PMOS都导通, OUT=1
*          │
*          ├─── OUT
*          │
*       MN1──MN2 (n18, 并联)
*       A─┤  B─┤    任一输入为1, 对应NMOS导通, OUT=0
*          │
*         VSS
*
* 注意: PMOS 串联宽度加倍 = W_P*2
*
* 晶体管数: 4
* ======================================================
.SUBCKT NOR2 A B OUT
MN1 OUT A VSS VSS n18 W={W_N} L={L_MIN}
MN2 OUT B VSS VSS n18 W={W_N} L={L_MIN}
MP1 OUT A N1 VDD p18 W={W_P*2} L={L_MIN}
MP2 N1 B VDD VDD p18 W={W_P*2} L={L_MIN}
.ENDS NOR2


* ======================================================
* 5. 或门 OR2 = NOR2 + INV
*
* 晶体管数: 6
* ======================================================
.SUBCKT OR2 A B OUT
XNOR A B NOR_OUT NOR2
XINV NOR_OUT OUT INV
.ENDS OR2


* ======================================================
* 6. 传输门 TG (Transmission Gate)
*
* 原理图:
*          IN
*           │
*       ┌───┤
*       │ MN (n18)   ── C (控制)
*       │ MP (p18)   ── C_N (反相控制)
*       └───┤
*           │
*          OUT
*
* 原理: C=1, C_N=0 → 两个晶体管都导通 → IN=OUT
*       C=0, C_N=1 → 两个晶体管都关断 → 高阻态
* 为什么用两个互补晶体管: NMOS 传强0弱1, PMOS 传强1弱0
*   并联后全摆幅传输
*
* 晶体管数: 2
* ======================================================
.SUBCKT TG IN OUT C C_N
MN1 OUT IN C_N VSS n18 W={W_N} L={L_MIN}
MP1 OUT IN C VDD p18 W={W_P} L={L_MIN}
.ENDS TG


* ======================================================
* 7. 同或门 XNOR2 (传输门风格)
*
* 逻辑: XNOR(A,B) = A⊙B = A·B + ~A·~B
*
* 结构: 传输门 + 反相器
*   A=0 → TG1导通 (B直通), TG2关断 → N1=B
*   A=1 → TG1关断, TG2导通 (B取反) → N1=~B
*   最后 N1 再经 INV_OUT 反相 → OUT=~N1
*
*   A=0,B=0: N1=0, OUT=1 = A⊙B
*   A=0,B=1: N1=1, OUT=0 = A⊙B
*   A=1,B=0: N1=1, OUT=0 = A⊙B
*   A=1,B=1: N1=0, OUT=1 = A⊙B
*
* 晶体管数: 10 (2 TG + 3 INV)
* ======================================================
.SUBCKT XNOR2 A B OUT
XINV_A A A_N INV          * 产生 A_N
XINV_B B B_N INV          * 产生 B_N
* TG1: A=0 → B 直通到 N1
XTG1 B N1 A A_N TG
* TG2: A=1 → ~B 直通到 N1
XTG2 B_N N1 A_N A TG
* 输出缓冲 (N1 反相后输出)
XINV_OUT N1 OUT INV
.ENDS XNOR2


* ======================================================
* 8. 异或门 XOR2 = XNOR2 + INV
*
* 逻辑: XOR(A,B) = A⊕B = ~(A⊙B)
*
* 晶体管数: 12
* ======================================================
.SUBCKT XOR2 A B OUT
XXOR A B XOR_OUT XNOR2
XINV XOR_OUT OUT INV
.ENDS XOR2


* ======================================================
* 9. 二选一多路选择器 MUX2to1 (修正版)
*
* 逻辑: Y = D0 (SEL=0) ; Y = D1 (SEL=1)
*
* 结构: 2 个传输门 + 1 个反相器
*   SEL=0 → TG1导通 (D0→Y), TG2关断
*   SEL=1 → TG1关断, TG2导通 (D1→Y)
*
* 晶体管数: 2TG + 1INV = 2×2 + 2 = 6
* ======================================================
.SUBCKT MUX2to1_CORRECT D0 D1 SEL Y
XINV_SEL SEL SEL_N INV
* TG1: SEL=0 → D0 通过 (经过 INV 后再 TG)
* TG2: SEL=1 → D1 通过
* 使用 PMOS 接 SEL, NMOS 接 SEL_N 实现正确控制
XTG0 D0 Y SEL_N SEL TG
XTG1 D1 Y SEL SEL_N TG
.ENDS MUX2to1_CORRECT


* ======================================================
* 10. D 触发器 DFF (主从结构, 上升沿触发)
*
* 结构:
*    ┌──── TG1 ── INV1 ── INV2 ── TG3 ──┬── INV3 ── INV4 ── TG4 ──┐
*    │         (主级)                    │    (从级)                │
*    D─┤                          ├──────────┤                     │
*    │  CLK=0: 主采样, 从保持     │         CLK=1: 主保持, 从输出 │
*    └──── TG2 ───────────────────┘         └──────────────────────┘
*
* CLK=0: TG1通, TG2断, TG3断, TG4通 → 主级跟踪D, 从级保持
* CLK↑:  TG1断, TG2通, TG3通, TG4断 → 主级锁存, 从级取主级值
*
* 输入: D, CLK
* 输出: Q, Q_N
* 晶体管数: 4TG + 7INV = 8 + 14 = 22 (业内通常计为 ~24 因含buffer)
* ======================================================
.SUBCKT DFF D CLK Q Q_N

* 时钟反相
XINV_CLK CLK CLK_N INV

* ---- 主级 (Master) ----
* TG1: CLK=0 导通 → D 采样
XTG_MAIN_IN D M_CLK CLK_N CLK TG
* INV1 + INV2: 锁存环 (CLK=1 时 TG2 导通形成保持)
XINV_M1 M_CLK M_INV1 INV
XINV_M2 M_INV1 M_INV2 INV
* TG2: CLK=1 导通 → 反馈保持
XTG_MAIN_FB M_INV2 M_CLK CLK CLK_N TG

* ---- 从级 (Slave) ----
* TG3: CLK=1 导通 → 主级值传给从级
XTG_SLV_IN M_INV1 S_CLK CLK CLK_N TG
* INV3 + INV4: 从级锁存环
XINV_S1 S_CLK S_INV1 INV
XINV_S2 S_INV1 S_INV2 INV
* TG4: CLK=0 导通 → 从级保持
XTG_SLV_FB S_INV2 S_CLK CLK_N CLK TG

* ---- 输出缓冲 ----
XINV_Q S_INV1 Q INV
XINV_QN Q Q_N INV

.ENDS DFF


* ======================================================
* 11. 带清零的 D 触发器 DFF_CLR
*
* 结构: DFF + AND2 (D_GATED = D & ~CLR)
* CLR=1 → D_GATED=0 → 下一 CLK↑ Q=0
*
* 晶体管数: DFF(24) + AND2(6) ≈ 28
* ======================================================
.SUBCKT DFF_CLR D CLK CLR Q Q_N
* 清零: CLR=1 时强制 D_GATED=0
XINV_CLR CLR CLR_N INV
XAND_GATE D CLR_N D_GATED AND2
* DFF 输出
XDFF D_GATED CLK Q Q_N DFF
.ENDS DFF_CLR


* ======================================================
* 12. 4 位寄存器 REG4
*
* 功能: 4 个 DFF_CLR 并联, 共享 CLK 和 CLR
* 输入: D[3:0], CLK, CLR
* 输出: Q[3:0]
* 晶体管数: 4 × 28 = 112
* ======================================================
.SUBCKT REG4 D3 D2 D1 D0 CLK CLR Q3 Q2 Q1 Q0
XDFF0 D0 CLK CLR Q0 Q0_N DFF_CLR
XDFF1 D1 CLK CLR Q1 Q1_N DFF_CLR
XDFF2 D2 CLK CLR Q2 Q2_N DFF_CLR
XDFF3 D3 CLK CLR Q3 Q3_N DFF_CLR
.ENDS REG4


* ======================================================
* 13. 4 位寄存器 (无清零) REG4_NOCLR
*
* 晶体管数: 4 × 24 = 96
* ======================================================
.SUBCKT REG4_NOCLR D3 D2 D1 D0 CLK Q3 Q2 Q1 Q0
XDFF0 D0 CLK Q0 Q0_N DFF
XDFF1 D1 CLK Q1 Q1_N DFF
XDFF2 D2 CLK Q2 Q2_N DFF
XDFF3 D3 CLK Q3 Q3_N DFF
.ENDS REG4_NOCLR

* ===== END =====
