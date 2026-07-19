* =========================================================
* Testbench: SNN-IF 神经元功能验证 (SMIC18MMRF)
*
* 场景: W=2 (0010), Vth=3 (0011)
* 脉冲序列: 1,1,1,0,0,0,1,1,...
*
* 预期膜电位:
*   T | SPIKE | V   | SPIKE_OUT
*   0 | 初始  | 0000| 0 (复位中)
*   1 | 1     | 0010| 0 (V=2 < Vth=3)
*   2 | 1     | 0100| 1 (V=4 >= Vth=3 → 触发)
*   3 | 1     | 0010| 0 (已复位, 再次积分)
*   4 | 0     | 0000| 0
* =========================================================

.INCLUDE '00_technology.sp'
.INCLUDE '01_basic_gates.sp'
.INCLUDE '03_snn_neuron.sp'


* ---- 时钟 (10MHz) ----
VCLK CLK 0 PULSE(0 {VDD} 0 1n 1n 50n 100n)

* ---- 全局复位 ----
VCLR CLR 0 PWL(0 {VDD} 140n {VDD} 150n 0)

* ---- W = 2 (0010) ----
VW3 W3 0 DC 0
VW2 W2 0 DC 0
VW1 W1 0 DC {VDD}
VW0 W0 0 DC 0

* ---- Vth = 3 (0011) ----
VVTH3 VTH3 0 DC 0
VVTH2 VTH2 0 DC 0
VVTH1 VTH1 0 DC {VDD}
VVTH0 VTH0 0 DC {VDD}

* ---- 脉冲序列 ----
VSPIKE SPIKE_IN 0 PWL(
+ 0n    0
+ 0n    {VDD}  1n 1n
+ 100n  0     101n 101n
+ 100n  {VDD} 101n 101n
+ 200n  0     201n 201n
+ 200n  {VDD} 201n 201n
+ 300n  0     301n 301n
+ 400n  0     401n 401n
+ 500n  0     501n 501n
+ 500n  {VDD} 501n 501n
+ 600n  0     601n 601n
+ 600n  {VDD} 601n 601n
+ 700n  0     701n 701n
+ 700n  0
)

* ---- IF 神经元 ----
XIF_NEURON W3 W2 W1 W0 SPIKE_IN CLK CLR VTH3 VTH2 VTH1 VTH0 V3 V2 V1 V0 SPIKE_OUT IF_NEURON_FULL

* ---- 仿真 ----
.TRAN 1n 1000n
.PRINT TRAN V(SPIKE_IN) V(V3) V(V2) V(V1) V(V0) V(SPIKE_OUT) V(CLK)

.OPTIONS POST=2 PROBE
.PROBE V(*)
.END
