* ======================================================
* SMIC18MMRF 工艺设定
* PDK: SMIC 0.18μm Mixed-Signal RF
* 器件: n18 (NMOS), p18 (PMOS)
* 供电: VDD = 1.8V
* ======================================================

* ---- 全局供电电压 ----
.PARAM VDD=1.8

* ---- 全局地线 ----
VSUPPLY VDD 0 {VDD}

* ---- 包含 PDK 模型库 ----
* 注意: 根据你的 PDK 实际路径修改以下 .INCLUDE
* 典型路径: /home/smic18mmrf/models/hspice/smic18mmrf_typ.sp
* 或
* .LIB '/home/cadence/smic18mmrf/libs/smic18mmrf.lib' TT
*
* 使用 Virtuoso ADE 仿真时, 在 Setup → Model Libraries 中添加 PDK 库
* 此处仅留作占位:
* .INCLUDE /path/to/smic18mmrf/models/hspice/smic18mmrf_n18.pm

* ---- 默认晶体管尺寸 ----
* 180nm 工艺最小 L, 典型 W
.PARAM L_MIN=0.18u
.PARAM W_N=0.5u
.PARAM W_P=1.0u

* ---- 后缀: 用于快速调用 ----
* 默认 NMOS: n18 W=W_N L=L_MIN
* 默认 PMOS: p18 W=W_P L=L_MIN

* ---- 全局节点 ----
.GLOBAL VDD VSS
