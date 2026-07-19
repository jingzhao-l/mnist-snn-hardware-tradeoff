* =========================================================
* Testbench: ANN-MAC 单元功能验证 (SMIC18MMRF)
* 仿真: ngspice -b testbench_mac.sp
* 或在 Virtuoso ADE L 中 Include 后运行
* =========================================================

.INCLUDE '00_technology.sp'
.INCLUDE '01_basic_gates.sp'
.INCLUDE '02_arithmetic.sp'


* ---- 时钟 100ns (10MHz) ----
VCLK CLK 0 PULSE(0 {VDD} 0 1n 1n 50n 100n)

* ---- 复位 150ns ----
VCLR CLR 0 PWL(0 {VDD} 140n {VDD} 150n 0)

* ---- A=3 (0011), B=5 (0101) ----
VA3 A3 0 DC 0
VA2 A2 0 DC 0
VA1 A1 0 PWL(0 0 200n {VDD})
VA0 A0 0 PWL(0 {VDD} 200n {VDD})

VB3 B3 0 DC 0
VB2 B2 0 PWL(0 {VDD} 200n {VDD})
VB1 B1 0 DC 0
VB0 B0 0 PWL(0 {VDD} 200n {VDD})

* ---- MAC 实例 ----
XMAC A3 A2 A1 A0 B3 B2 B1 B0 CLK CLR ACC3 ACC2 ACC1 ACC0 COUT MAC

* ---- 仿真 ----
.TRAN 1n 500n
.PRINT TRAN V(ACC3) V(ACC2) V(ACC1) V(ACC0) V(COUT) V(CLK)

* 预期:
*   200ns CLK↑:  乘积15 + ACC(0) = 15 → ACC=1111
*   300ns CLK↑:  乘积15 + ACC(15) = 30 → ACC=1110, COUT=1
*   400ns CLK↑:  继续累加

.OPTIONS POST=2 PROBE
.PROBE V(*)
.END
