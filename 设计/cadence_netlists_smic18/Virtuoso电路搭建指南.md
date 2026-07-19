# Cadence Virtuoso 电路搭建指南 — 从 nMOS/pMOS 到完整 SNN 与 ANN 电路

**工艺**: SMIC18MMRF (n18/p18, VDD=1.8V, L=0.18μm)  
**对应**: 详细实施设计方案 第四·五章  
**适用**: 自行在 Virtuoso Schematic Editor (VSE) 中绘制

---

## 完整的基本单元清单

你说得对, 我列的 6 个 (INV, NAND2, XOR2, TG, DFF, FA) 只是**练习上手的前 6 个**, 并不是全部。以下是完整清单, 层级分明。

### 层级一: 晶体管级单元 (不可再分, 共 4 个)

这 4 个是真正的**最小单元**, 由 n18/p18 直接搭成。其余全部是它们的排列组合。建议你**第一个画 INV 验证工艺库能不能正常工作**。

| 编号 | 单元 | 晶体管数 | 用于构造 |
|:---:|:---:|:--------:|:--------|
| 1 | **INV** | 2 | AND2, OR2, XOR2, DFF, 几乎万物 |
| 2 | **NAND2** | 4 | AND2, (理论上能搭万物但效率低) |
| 3 | **NOR2** | 4 | OR2, (同上) |
| 4 | **TG** | 2 | XNOR2, MUX2to1, DFF |

> **核心理解**: 为什么上面 4 个就够了？  
> NAND2 和 NOR2 各自本身就是"通用门", 能搭任何组合逻辑 (大学数字电路第一课学的门电路完备性)。TG 是开关, 处理存储和选通。INV 是恢复信号幅度。**整个 MAC 800 管和 IF 神经元 500 管, 全部是这 4 个单元的组合。**

**VSE 操作对比:**
- INV: 放 1 个 n18 + 1 个 p18, 连 4 条线
- NAND2: 放 2 个 n18 + 2 个 p18, 连 8 条线
- TG: 放 1 个 n18 + 1 个 p18, 源漏接在一起

### 层级二: 基本逻辑门 (共 5 个)

| 编号 | 单元 | 晶体管数 | 构造方式 |
|:---:|:---:|:--------:|:--------|
| 5 | **AND2** | 6 | NAND2 + INV |
| 6 | **OR2** | 6 | NOR2 + INV |
| 7 | **XNOR2** | 10 | 2×TG + 3×INV (传输门风格, 详见下文) |
| 8 | **XOR2** | 12 | XNOR2 + INV (真正异或) |
| 9 | **MUX2to1** | 6 | 2×TG + INV |
| 10 | **XNOR2/XOR2 的替代方案** | 10/12 | 4×NAND2 (不推荐, 管数多) |

**最重要的结构区别:**

**AND2 是 NAND2 + INV:**
```
A ──┬───  NAND2  ──┬──  INV  ── OUT
B ──┘              │
                   └── (NAND 内部才有晶体管)
```
你打开 NAND2 内部看到 4 个管, 再外面包一层 INV 就是 AND2。

**XNOR2 与 XOR2 的实现:**

基础单元是 XNOR2（传输门风格, 10T）:
```
       ┌── TG1 ──┐
A=0 ──┤         ├─── N1 ──→[INV]──→ OUT = A XNOR B
       └── TG2 ──┘
A=1 ──→   ↑
       B_N (B 经过 INV_B 再连到 TG2 输入)
```
TG1: C=A, C_N=A_N; TG2: C=A_N, C_N=A
TG1 与 TG2 输出短接于节点 N1，经 INV_OUT 输出。

真正的 XOR2 只需在 XNOR2 后再加一级 INV:
`XOR = ~(A XNOR B)`

方法三 (NAND 风格, 16T, 不推荐):
`XOR = (A NAND (A NAND B)) NAND (B NAND (A NAND B))` — 用了 4 个 NAND 但速度慢

### 层级三: 时序与存储单元 (共 3 个)

| 编号 | 单元 | 晶体管数 | 构造方式 |
|:---:|:---:|:--------:|:--------|
| 11 | **DFF** | ~22 (≈24) | 4×TG + 7×INV (主从结构: 主级2INV+从级2INV+时钟反相1+输出缓冲2) |
| 12 | **DFF_CLR** | ~28 | DFF + AND2 (清零: D & ~CLR) |
| 13 | **REG4** | ~112 | 4×DFF_CLR 拼成 4 位总线 |

**DFF 是 Virtuoso 里最难画对的结构, 务必对照这个时序图接线:**

```
主级采样段 (CLK=1):         主级锁存段 (CLK=0):
    D ─ TG1开 ─ INV1 ─ INV2 ─ TG3开 ─ INV3 ─ INV4 ─ Q
              │                  ↑
          TG2关 ── 反馈环      TG4关 ── 反馈环
```

接线规则:
- TG1: C=CLK_N, C_N=CLK (CLK=1 时导通, D 进入主级)
- TG2: C=CLK,   C_N=CLK_N (CLK=0 时反馈锁存)
- TG3: C=CLK,   C_N=CLK_N (CLK=0 时传给从级)
- TG4: C=CLK_N, C_N=CLK (CLK=1 时从级锁存)

> **TG 导通条件**: 因 TG 结构中 PMOS 栅=C, NMOS 栅=C_N, 故 C=0 且 C_N=1 时导通。CLK=1 时 CLK_N=0, 所以接 C=CLK_N 的 TG(如 TG1)在 CLK=1 时导通。

### 层级四: 算术单元 (共 4 个)

| 编号 | 单元 | 晶体管数 | 构造方式 |
|:---:|:---:|:--------:|:--------|
| 14 | **HA (半加器)** | ~18 | XOR2 + AND2 |
| 15 | **FA (全加器)** | ~42 | 2×XOR2 + 2×AND2 + OR2 |
| 16 | **CLA4 (超前进位加法器)** | ~300 | 8×AND2 + 8×XOR2 + ~16×AND2/OR2 |
| 17 | **ADD4 (行波进位加法器)** | ~120 | 4×FA 串联 |

**FA 的接线 (记住这三个公式就够)：**
```
SUM  = A ⊕ B ⊕ CIN
COUT = (A·B)         ← A 和 B 都为 1
     | (CIN · (A⊕B))  ← 进位传递
```
画 FA 时建立 1 个 cellview, 内部放 2 个 XOR2、2 个 AND2、1 个 OR2, 按公式连线。

### 层级五: 乘法器与完整模块 (共 6 个)

| 编号 | 单元 | 晶体管数 | 构造方式 |
|:---:|:---:|:--------:|:--------|
| 18 | **4×4 ARRAY_MULT** | ~504 | 16×AND2 + 4×HA + 8×FA |
| 19 | **CMP_GE** | ~160 | XOR2 + AND2 + OR2 + INV |
| 20 | **MUX4** | ~32 | 4×MUX2to1 + 4×INV |
| 21 | **IF_INTEGRATOR** | ~312 | MUX4 + ADD4 + REG4 |
| 22 | **IF_NEURON_FULL** | ~496 | IF_INTEGRATOR + CMP_GE + SYNC_RESET |
| 23 | **MAC** | ~916 | ARRAY_MULT_4X4 + CLA4 + REG4 |

---

## Virtuoso 实操指南 (步骤详解)

### 第一步: 建立工艺库

1. 打开 Virtuoso CIW (命令行窗口)
2. `Tools → Library Manager`
3. `File → New → Library`
4. Name: `SNN_PROJECT`
5. **Attach to existing technology library** → 选择 `smic18mmrf`
6. OK

### 第二步: 从 INV 开始搭 (验证库能工作)

**创建 cell:**
1. Library Manager 中选中 `SNN_PROJECT`
2. `File → New → Cell View`
3. Cell Name: `INV`, View: `schematic`, Tool: `Composer-Schematic`
4. OK

**放置晶体管:**
1. 快捷键 `i` (Instance) 或菜单 Create → Instance
2. Browse → 选 `smic18mmrf` → `n18` 
3. 参数: Width=`500n`, Length=`180n`
4. 放在画布**下**半区
5. 再放一次, Browse → `p18`
6. 参数: Width=`1u`, Length=`180n`
7. 放在画布**上**半区 (PMOS 总是放上面)

**连线:**
1. 先打 VDD/VSS 的 pin，便于后面接线有地可接:
   - `p`: Name=`VDD`, Direction=`inputOutput`, 放在画布上方
   - `p`: Name=`VSS`, Direction=`inputOutput`, 放在画布下方
2. `p18` 的源极 (Source) → 直接画线连到 `VDD` pin (同一根线, 不可断)
3. `n18` 的源极 (Source) → 直接画线连到 `VSS` pin (同一根线, 不可断)
4. `p18` 和 `n18` 的栅极 (Gate) → 画一条竖线连起来 → 在这根线上打 pin `IN` (input)
5. `p18` 和 `n18` 的漏极 (Drain) → 画一条竖线连起来 → 在这根线上打 pin `OUT` (output)

> **关键**: VDD pin 必须和 p18 Source 是**同一根线**，不能 VDD pin 打在某处但和 p18 Source 之间没有物理连线。同理 VSS pin 必须和 n18 Source 是同一根线。这是新手最容易犯的错：打了 pin 但晶体管没连过去。

**保存:** 快捷键 `F8` (Check and Save)

**验证:** 要确保 `n18` 的 bulk(body) 接 VSS, `p18` 的 bulk 接 VDD。SMIC 库通常自动处理, 但如果仿真报错, 需要手动加。另外务必在 schematic 里检查 **VDD pin → p18 Source** 和 **VSS pin → n18 Source** 是同一根物理连线，没有断开。这是 INV 仿真输出不正常的头号原因。

> 如果 INV 能 Check and Save 通过, 说明你的 PDK 安装正确, 可以继续往下。

### 第三步: TG (传输门)

1. 新建 cell `TG`
2. 放 1 个 n18 (W=`500n`, L=`180n`), 1 个 p18 (W=`1u`, L=`180n`)
3. **关键: n18 和 p18 的源漏短接**
   - n18 的 Source + p18 的 Source = `IN` (画同一根线)
   - n18 的 Drain + p18 的 Drain = `OUT`
4. n18 的 Gate = `C_N` (控制反相)
5. p18 的 Gate = `C` (控制)
6. n18 body = VSS, p18 body = VDD
7. 打 Pin: `IN`, `OUT`, `C`, `C_N`, `VDD`, `VSS`

### 第四步: NAND2

1. 新建 cell `NAND2`
2. 放 2 个 p18 (并联):
   - 参数: Width=`1u`, Length=`180n`
   - p18_A: Gate=A, Source=VDD, Drain=OUT
   - p18_B: Gate=B, Source=VDD, Drain=OUT
3. 放 2 个 n18 (串联):
   - 参数: Width=`1u`, Length=`180n`  (串联电阻加倍, 宽度加倍补偿)
   - n18_A: Gate=A, Drain=OUT, Source=N1 (中间节点)
   - n18_B: Gate=B, Drain=N1, Source=VSS
4. 打 Pin: `A`, `B`, `OUT`, `VDD`, `VSS`

### 第五步: NOR2

1. 新建 cell `NOR2`
2. 放 2 个 n18 (并联):
   - 参数: Width=`500n`, Length=`180n`
   - n18_A: Gate=A, Drain=OUT, Source=VSS
   - n18_B: Gate=B, Drain=OUT, Source=VSS
3. 放 2 个 p18 (串联):
   - 参数: Width=`2u`, Length=`180n`  (串联电阻加倍, 宽度加倍补偿)
   - p18_A: Gate=A, Source=VDD, Drain=N1 (中间节点)
   - p18_B: Gate=B, Source=N1, Drain=OUT
4. 打 Pin: `A`, `B`, `OUT`, `VDD`, `VSS`

### 第六步: AND2 (NAND2 + INV)

1. 新建 cell `AND2`
2. Instance 1 个 `NAND2`, 1 个 `INV`
3. 接线:
   ```
   A ──┐
       ├──→ NAND2 ──→ NAND_OUT ──→ INV ──→ OUT
   B ──┘
   ```
4. 打 Pin: `A`, `B`, `OUT`, `VDD`, `VSS`

### 第七步: OR2 (NOR2 + INV)

1. 新建 cell `OR2`
2. Instance 1 个 `NOR2`, 1 个 `INV`
3. 接线:
   ```
   A ──┐
       ├──→ NOR2 ──→ NOR_OUT ──→ INV ──→ OUT
   B ──┘
   ```
4. 打 Pin: `A`, `B`, `OUT`, `VDD`, `VSS`

### 第八步: XNOR2 (传输门风格, 10T)

1. 新建 cell `XNOR2`
2. Instance 3 个 INV、2 个 TG
3. 接线:
   ```
   INV_A: IN→A, OUT→A_N
   INV_B: IN→B, OUT→B_N

   TG1: IN→B,  OUT→N1, C=A,   C_N=A_N  (A=0 时导通, B 直通)
   TG2: IN→B_N, OUT→N1, C=A_N, C_N=A    (A=1 时导通, ~B 通过)

   N1 → INV_OUT → XNOR_OUT
   ```

   即 TG1 和 TG2 输出短接在节点 `N1`，再经过 `INV_OUT` 得到最终输出。

| 线名 | 起点 | 终点 |
|:---|:---|:---|
| A | 外部 pin `A` | INV_A 输入, TG1.C, TG2.C_N |
| A_N | INV_A 输出 | TG1.C_N, TG2.C |
| B | 外部 pin `B` | INV_B 输入, TG1.IN |
| B_N | INV_B 输出 | TG2.IN |
| N1 | TG1.OUT, TG2.OUT (短接) | INV_OUT 输入 |
| XNOR_OUT | INV_OUT 输出 | 外部 pin `OUT` |

4. 打 Pin: `A`, `B`, `OUT`, `VDD`, `VSS`

> **XNOR2 输出**: OUT = A ⊙ B = A XNOR B。这是 2×TG + 3×INV 传输门结构的直接输出。

### 第九步: XOR2 (真正异或, 12T)

1. 新建 cell `XOR2`
2. Instance 1 个 `XNOR2`, 1 个 `INV`
3. 接线:
   ```
   A ──┬──→[XNOR2]──→ XNOR_OUT ──→[INV]──→ OUT
   B ──┘
   ```

| 线名 | 起点 | 终点 |
|:---|:---|:---|
| A | 外部 pin `A` | XNOR2.A |
| B | 外部 pin `B` | XNOR2.B |
| XNOR_OUT | XNOR2.OUT | INV 输入 |
| OUT | INV 输出 | 外部 pin `OUT` |

4. 打 Pin: `A`, `B`, `OUT`, `VDD`, `VSS`

> **XOR2 输出**: OUT = A ⊕ B = ~(A XNOR B)。
> 
> **重要**: `HA`, `FA`, `CLA4`, `CMP_GE` 这些电路内部需要的是真正的 XOR，因此它们应调用本步骤的 `XOR2`，而不是 `XNOR2`。`XNOR2` 主要作为 `XOR2` 的构建单元使用。

### 第十步: DFF (~22 管, 整项目最复杂的单 cell)

1. 新建 cell `DFF`
2. Instance 7 个 INV, 分别命名为 (名字要对, 后面接线用):
   - `INV_CLK`: 时钟反相
   - `INV1`, `INV2`: 主级锁存环
   - `INV3`, `INV4`: 从级锁存环
   - `INV_Q`: Q 输出缓冲
   - `INV_QN`: Q_N 输出缓冲
3. Instance 4 个 TG, 分别命名为 `TG1`, `TG2`, `TG3`, `TG4`
4. 按下面表格一条条连:

**核心锁存接线表:**

| 管线 | 起点 | 终点 |
|:---|:---|:---|
| TG1_IN | D | TG1 输入 |
| TG1_OUT | TG1 输出 | INV1 输入 |
| INV1_OUT | INV1 输出 | INV2 输入, TG3 输入 |
| INV2_OUT | INV2 输出 | TG2 输入 |
| TG2_OUT | TG2 输出 | INV1 输入 (主级反馈环) |
| TG3_OUT | TG3 输出 | INV3 输入 |
| INV3_OUT | INV3 输出 | INV4 输入, INV_Q 输入 |
| INV4_OUT | INV4 输出 | TG4 输入 |
| TG4_OUT | TG4 输出 | INV3 输入 (从级反馈环) |

**时钟接线表:**

| 管线 | 起点 | 终点 |
|:---|:---|:---|
| CLK_IN | 外部 pin `CLK` | INV_CLK 输入 |
| CLK_N | INV_CLK 输出 | TG1 的 C, TG4 的 C |
| CLK | 外部 pin `CLK` | TG2 的 C, TG3 的 C |

即:
- TG1: C = CLK_N, C_N = CLK
- TG2: C = CLK,   C_N = CLK_N
- TG3: C = CLK,   C_N = CLK_N
- TG4: C = CLK_N, C_N = CLK

**输出接线表:**

| 管线 | 起点 | 终点 |
|:---|:---|:---|
| S_INV1 | INV3 输出 | INV4 输入, INV_Q 输入 |
| Q | INV_Q 输出 | 外部 pin `Q` |
| (Q 到 INV_QN) | 外部 pin `Q` | INV_QN 输入 |
| Q_N | INV_QN 输出 | 外部 pin `Q_N` |

即：`INV3 输出` 同时接 `INV4 输入` 和 `INV_Q 输入`；`INV_Q 输出 = Q`，Q 再接到 `INV_QN 输入`，得到 `Q_N`。

5. **打 Pin (外部引脚)**:

   DFF 对外只有 6 个 pin，其余全是内部 label:

   | Pin 名 | Direction | 说明 |
   |:---|:---:|:---|
   | `D` | input | 数据输入 |
   | `CLK` | input | 时钟输入 |
   | `Q` | output | 原相输出 |
   | `Q_N` | output | 反相输出 |
   | `VDD` | inputOutput | 电源 |
   | `VSS` | inputOutput | 地 |

   **内部 label（不是 pin，用 `l` 标，不要 Create → Pin）**:
   `CLK_N`, `M_CLK`, `M_INV1`, `M_INV2`, `S_CLK`, `S_INV1`, `S_INV2`

### 第十一步: FA (全加器, 算术单元核心)

FA = 2 个 XOR2 + 2 个 AND2 + 1 个 OR2。

#### 摆放位置建议 (VSE 画布布局)

```
        上半区 (组合逻辑)
   ┌─────────────────────────────┐
   │                             │
A ─┤──→[XOR1]──→ XOR_AB ──→[XOR2]──→ SUM
B ─┤──→[    ]              ↑    │
   │                         CIN ─┤
   │                             │
A ─┤──→[AND1]──→ C1 ──┐          │
B ─┤──→[    ]         │          │
   │                   ↓          │
XOR_AB ─→[AND2]──→ C2 ─→[OR2]──→ COUT
CIN ───→[    ]                  │
   │                             │
   └─────────────────────────────┘
```

#### 接线步骤

1. 新建 cell `FA`
2. Instance 2 个 `XOR2`, 2 个 `AND2`, 1 个 `OR2`
3. 按下面连:

| 线名 | 起点 | 终点 |
|:---|:---|:---|
| A | 外部 pin `A` | XOR1.A, AND1.A |
| B | 外部 pin `B` | XOR1.B, AND1.B |
| CIN | 外部 pin `CIN` | XOR2.B, AND2.B |
| XOR_AB | XOR1.OUT | XOR2.A, AND2.A |
| SUM | XOR2.OUT | 外部 pin `SUM` |
| C1 | AND1.OUT | OR2.A |
| C2 | AND2.OUT | OR2.B |
| COUT | OR2.OUT | 外部 pin `COUT` |

4. 打 Pin: `A`, `B`, `CIN`, `SUM`, `COUT`, `VDD`, `VSS`

#### 关键检查点

- `XOR_AB` 这个内部节点一定要连到 3 个地方: `XOR2.A`, `AND2.A`, 以及你加的 label
- `A` 和 `B` 各要连到 2 个门: `XOR1` 和 `AND1`
- `CIN` 各要连到 2 个门: `XOR2` 和 `AND2`

### 第十二步: HA (半加器)

FA 的前置单元，简单。

1. 新建 cell `HA`
2. Instance 1 个 `XOR2`, 1 个 `AND2`
3. 接线:
   ```
   A ──┬──→ [XOR2] ──→ SUM
   B ──┤
       │
       └──→ [AND2] ──→ COUT
   ```

| 线名 | 起点 | 终点 |
|:---|:---|:---|
| A | 外部 pin `A` | XOR2.A, AND2.A |
| B | 外部 pin `B` | XOR2.B, AND2.B |
| SUM | XOR2.OUT | 外部 pin `SUM` |
| COUT | AND2.OUT | 外部 pin `COUT` |

4. 打 Pin: `A`, `B`, `SUM`, `COUT`, `VDD`, `VSS`

### 第十三步: MUX2to1 (2 选 1 多路选择器)

1. 新建 cell `MUX2to1`
2. Instance 1 个 `INV`, 2 个 `TG`
3. 接线:
   ```
                      SEL ──→[INV]──→ SEL_N

        IN0 ──→[TG0]──┐
                      ├──→ MUX_OUT
        IN1 ──→[TG1]──┘

   TG0: C=SEL_N, C_N=SEL    (SEL=0 时导通 → 选 IN0)
   TG1: C=SEL,   C_N=SEL_N  (SEL=1 时导通 → 选 IN1)
   ```

| 线名 | 起点 | 终点 |
|:---|:---|:---|
| SEL | 外部 pin `SEL` | INV 输入, TG1.C |
| SEL_N | INV 输出 | TG0.C, TG1.C_N |
| IN0 | 外部 pin `IN0` | TG0 输入 |
| IN1 | 外部 pin `IN1` | TG1 输入 |
| MUX_OUT | TG0 输出, TG1 输出 (短接) | 外部 pin `OUT` |

4. 打 Pin: `IN0`, `IN1`, `SEL`, `OUT`, `VDD`, `VSS`

### 第十四步: DFF_CLR (带清零的 DFF)

1. 新建 cell `DFF_CLR`
2. Instance 1 个 `DFF`, 1 个 `AND2`, 1 个 `INV` (反相 CLR)
3. 接线:
   ```
   CLR ──→ [INV] ──→ ~CLR

        D ──→ [AND2] ──→ D_GATED ──→ [DFF] ──→ Q
   ~CLR ──→                                        Q_N
   ```

   INV: IN=CLR, OUT=~CLR
   AND2: A=D, B=~CLR → D_GATED
   DFF: D=D_GATED, CLK=CLK → Q, Q_N

   当 CLR=1 时 ~CLR=0，AND2 输出=0 → DFF 锁存 0 → Q=0。

4. 打 Pin: `D`, `CLK`, `CLR`, `Q`, `Q_N`, `VDD`, `VSS`

### 第十五步: REG4 (4 位总线寄存器)

REG4 就是把 4 个 DFF_CLR 并排放。注意：**D 和 Q 每位独立**，只有 CLK、CLR 共享。

1. 新建 cell `REG4`
2. Instance 4 个 `DFF_CLR`
3. 分别接:

   | DFF | D | CLK | CLR | Q | Q_N |
   |:---|:---|:---|:---|:---|:---|
   | DFF0 | D[0] | CLK | CLR | Q[0] | (悬空, 不接) |
   | DFF1 | D[1] | CLK | CLR | Q[1] | (悬空, 不接) |
   | DFF2 | D[2] | CLK | CLR | Q[2] | (悬空, 不接) |
   | DFF3 | D[3] | CLK | CLR | Q[3] | (悬空, 不接) |

   即：
   - `CLK` 一根线连到 4 个 DFF_CLR 的 CLK
   - `CLR` 一根线连到 4 个 DFF_CLR 的 CLR
   - `D[0]` 只连 DFF0.D，`Q[0]` 只连 DFF0.Q，不要串到 DFF1
   - `Q_N` 输出在本单元不用，悬空即可m

4. 打 Pin: `D[3:0]` (4 个 input), `CLK`, `CLR`, `Q[3:0]` (4 个 output), `VDD`, `VSS`

### 第十六步: ADD4 (4 位行波进位加法器, 用于 SNN)

1. 新建 cell `ADD4`
2. Instance 4 个 `FA` (串联)
3. 接线:
   ```
        A0 B0     A1 B1     A2 B2     A3 B3
         │ │       │ │       │ │       │ │
         ↓ ↓  C1   ↓ ↓  C2   ↓ ↓  C3   ↓ ↓
   CIN─→[FA0]─→[FA1]─→[FA2]─→[FA3]──→ COUT
         │        │        │        │
         S0       S1       S2       S3
   ```

| 线 | 起点 | 终点 |
|:---|:---|:---|
| CIN | 外部 pin `CIN` | FA0.CIN |
| C1 | FA0.COUT | FA1.CIN |
| C2 | FA1.COUT | FA2.CIN |
| C3 | FA2.COUT | FA3.CIN |
| COUT | FA3.COUT | 外部 pin `COUT` |
| S[3:0] | FA0-3.SUM | 外部 pin `S[3:0]` |
| A[3:0], B[3:0] | 外部 pin | 各 FA 对应 A/B |

4. 打 Pin: `A[3:0]`, `B[3:0]`, `CIN`, `S[3:0]`, `COUT`, `VDD`, `VSS`

### 第十七步: CLA4 (超前进位加法器, 用于 MAC)

这一步需要最多的 AND2/OR2/XOR2 门数，按公式展开。

1. 新建 cell `CLA4`
2. Instance 4 个 `AND2`, 4 个 `XOR2` (G/P生成), 20 个 `AND2` + 10 个 `OR2` (进位链), 4 个 `XOR2` (求和)
3. 结构分三步:

#### 步骤 1: 产生项和传播项

```
A0 B0: G0 = AND2(A0,B0), P0 = XOR2(A0,B0)
A1 B1: G1 = AND2(A1,B1), P1 = XOR2(A1,B1)
A2 B2: G2 = AND2(A2,B2), P2 = XOR2(A2,B2)
A3 B3: G3 = AND2(A3,B3), P3 = XOR2(A3,B3)
```

#### 步骤 2: 超前进位链（逐门接线表）

**C1 = G0 OR (P0 · CIN)**

| 门 | 输入 A | 输入 B | 输出 |
|:---|:---|:---|:---|
| XAND_C1 | P0 | CIN | C1_AND |
| OR_C1 | G0 | C1_AND | C1 |

**C2 = G1 OR (P1 · G0) OR (P1 · P0 · CIN)**

| 门 | 输入 A | 输入 B | 输出 |
|:---|:---|:---|:---|
| XAND_C2A | P1 | G0 | C2_TERM1 |
| XAND_C2B | P1 | P0 | C2_TERM2 |
| XAND_C2C | C2_TERM2 | CIN | C2_TERM3 |
| OR_C2A | G1 | C2_TERM1 | C2_TMP |
| OR_C2B | C2_TMP | C2_TERM3 | C2 |

**C3 = G2 OR (P2 · G1) OR (P2 · P1 · G0) OR (P2 · P1 · P0 · CIN)**

| 门 | 输入 A | 输入 B | 输出 |
|:---|:---|:---|:---|
| XAND_C3A | P2 | G1 | C3_TERM1 |
| XAND_C3B | P2 | P1 | C3_TMP1 |
| XAND_C3C | C3_TMP1 | G0 | C3_TERM2 |
| XAND_C3D | P2 | P1 | C3_TMP2 |
| XAND_C3E | C3_TMP2 | P0 | C3_TMP3 |
| XAND_C3F | C3_TMP3 | CIN | C3_TERM3 |
| OR_C3A | G2 | C3_TERM1 | C3_TMP4 |
| OR_C3B | C3_TMP4 | C3_TERM2 | C3_TMP5 |
| OR_C3C | C3_TMP5 | C3_TERM3 | C3 |

**C4 = G3 OR (P3 · G2) OR (P3 · P2 · G1) OR (P3 · P2 · P1 · G0) OR (P3 · P2 · P1 · P0 · CIN)**

| 门 | 输入 A | 输入 B | 输出 |
|:---|:---|:---|:---|
| XAND_C4A | P3 | G2 | C4_TERM1 |
| XAND_C4B | P3 | P2 | C4_TMP1 |
| XAND_C4C | C4_TMP1 | G1 | C4_TERM2 |
| XAND_C4D | P3 | P2 | C4_TMP2 |
| XAND_C4E | C4_TMP2 | P1 | C4_TMP3 |
| XAND_C4F | C4_TMP3 | G0 | C4_TERM3 |
| XAND_C4G | P3 | P2 | C4_TMP4 |
| XAND_C4H | C4_TMP4 | P1 | C4_TMP5 |
| XAND_C4I | C4_TMP5 | P0 | C4_TMP6 |
| XAND_C4J | C4_TMP6 | CIN | C4_TERM4 |
| OR_C4A | G3 | C4_TERM1 | C4_TMP7 |
| OR_C4B | C4_TMP7 | C4_TERM2 | C4_TMP8 |
| OR_C4C | C4_TMP8 | C4_TERM3 | C4_TERM5 |
| OR_C4D | C4_TERM5 | C4_TERM4 | COUT |

#### 步骤 3: 求和

> **注意**: 下式中的 `C0` 就是外部输入 `CIN`，即 `C0 = CIN`。

```
S0 = P0 XOR C0 = P0 XOR CIN
S1 = P1 XOR C1
S2 = P2 XOR C2
S3 = P3 XOR C3
COUT = C4
```

4. 打 Pin: `A[3:0]`, `B[3:0]`, `CIN`, `S[3:0]`, `COUT`, `VDD`, `VSS`

**贴士**: 别一次画完再 Check。拆成 3 段，每段画完就 F8。进位网最密（C4 有 5 个 OR 项），细节对照 `02_arithmetic.sp` 中的 CLA4 逐条连。

> **关于冗余**: 本实现中 C3 的 `P2·P1` 和 C4 的 `P3·P2`、`P3·P2·P1` 被重复计算了多次。这样设计的好处是每个 AND2 只驱动一个负载、速度更快；缺点是多用 4 个 AND2（约 24 个晶体管）。如果你更看重面积，可以把这些中间结果共享，省到 20 AND2 + 8 XOR2 + 10 OR2（约 276T）。

### 第十八步: 4×4 阵列乘法器

整个项目门数最多的单 cell（16 AND2 + 4 HA + 8 FA = 28 个 subcell）。

#### 布局 (壁纸式)

```
            B3    B2    B1    B0
            │     │     │     │
     A0────→[AND] [AND] [AND] [AND] ←── P00-P03
     A1────→[AND] [AND] [AND] [AND] ←── P10-P13
     A2────→[AND] [AND] [AND] [AND] ←── P20-P23
     A3────→[AND] [AND] [AND] [AND] ←── P30-P33

          列0   列1   列2   列3   列4   列5   列6   列7
   P00──→Y0
          P01─→[HA]─→Y1
             C1─→[FA]─→S2─→[HA]─→Y2
                 C2─→[FA]─→S3A─→[HA]─→Y3
           P03,P30─→[FA]─→S3B
                     C3A─→[FA]─→S4A─→[FA]─→S4B─→[HA]─→Y4
               P31,C3B─→[FA]
                        C4A─→[FA]─→S5─→[FA]─→Y5
                    C4B,C4C─→[FA]
                           C5A─→[FA]─→Y6
                              C5B─→[OR2(VSS)]─→Y7
```

#### 步骤 1: 16 个 AND2 实例化命名表

| AND2 名 | A | B | 输出 |
|:---|:---|:---|:---|
| XAND00 | A0 | B0 | P00 |
| XAND01 | A0 | B1 | P01 |
| XAND02 | A0 | B2 | P02 |
| XAND03 | A0 | B3 | P03 |
| XAND10 | A1 | B0 | P10 |
| XAND11 | A1 | B1 | P11 |
| XAND12 | A1 | B2 | P12 |
| XAND13 | A1 | B3 | P13 |
| XAND20 | A2 | B0 | P20 |
| XAND21 | A2 | B1 | P21 |
| XAND22 | A2 | B2 | P22 |
| XAND23 | A2 | B3 | P23 |
| XAND30 | A3 | B0 | P30 |
| XAND31 | A3 | B1 | P31 |
| XAND32 | A3 | B2 | P32 |
| XAND33 | A3 | B3 | P33 |

#### 步骤 2: HA/FA 实例化接线表 (逐列级联)

| 列 | 加法器 | 输入 | 输出 |
|:---|:---|:---|:---|
| 0 | AND2(VDD) | P00, VDD | Y0 |
| 1 | HA_COL1 | P01, P10 | Y1, C1_COL1 |
| 2 | FA_COL2 | P11, P20, C1_COL1 | S2_COL2, C2_COL2 |
| 2 | HA_COL2 | S2_COL2, P02 | Y2, C_DUMMY2 |
| 3 | FA_COL3A | P12, P21, C2_COL2 | S3A, C3A |
| 3 | FA_COL3B | P03, P30, C_DUMMY2 | S3B, C3B |
| 3 | HA_COL3 | S3A, S3B | Y3, C3C |
| 4 | FA_COL4A | P13, P22, C3A | S4A, C4A |
| 4 | FA_COL4B | S4A, P31, C3B | S4B, C4B |
| 4 | HA_COL4 | S4B, C3C | Y4, C4C |
| 5 | FA_COL5A | P23, P32, C4A | S5, C5A |
| 5 | FA_COL5B | S5, C4B, C4C | Y5, C5B |
| 6 | FA_COL6 | P33, C5A, C5B | Y6, C6 |
| 7 | AND2(VDD) | C6, VDD | Y7 |

**列 0**: 用 1 个 AND2，A=P00, B=VDD → OUT = P00 (缓冲)。

**列 7**: 用 1 个 AND2，A=C6, B=VDD → OUT = C6 (缓冲)。

**最容易接错**: 列 3 和列 4 的 C_DUMMY2、C3A、C3B、C3C 之间进位交叉。每个 FA/HA 的 3 个输入要严格对上表。

#### 步骤 3: 打 Pin

`A3`, `A2`, `A1`, `A0`, `B3`, `B2`, `B1`, `B0`, `Y7`...`Y0`, `VDD`, `VSS`

### 第十九步: MAC 顶层

MAC = 1 个 ARRAY_MULT_4X4 + 1 个 CLA4 + 1 个 REG4。

#### 接线表

| Step | 子电路 | 输入 | 输出 |
|:---|:---|:---|:---|
| 1 | `ARRAY_MULT_4X4` | A[3:0], B[3:0] | Y[7:0] |
| 2 | `CLA4` | A=Y[3:0], B=ACC[3:0] (REG4 输出), CIN=0 | S[3:0], COUT_INT |
| 3 | `REG4` | D=S[3:0], CLK, CLR | Q=ACC[3:0] |
| 4 | `OR2` | A=COUT_INT, B=VSS  | OUT=COUT |

#### 关键连线

```
外部 pin A[3:0] ──→ ARRAY_MULT.A[3:0]
外部 pin B[3:0] ──→ ARRAY_MULT.B[3:0]
外部 pin CLK    ──→ REG4.CLK
外部 pin CLR    ──→ REG4.CLR

ARRAY_MULT.Y[3:0] ──→ CLA4.A[3:0]
ARRAY_MULT.Y[7:4] ──→ (悬空, 不连)
REG4.Q[3:0]       ──→ CLA4.B[3:0]          ← 累加器反馈
CLA4.S[3:0]       ──→ REG4.D[3:0]
CLA4.COUT         ──→ OR2.A                ← COUT = COUT_INT OR 0
OR2.OUT           ──→ 外部 pin COUT
REG4.Q[3:0]       ──→ 外部 pin ACC[3:0]
```

#### 打 Pin

`A3`, `A2`, `A1`, `A0`, `B3`, `B2`, `B1`, `B0`, `CLK`, `CLR`, `ACC3`, `ACC2`, `ACC1`, `ACC0`, `COUT`, `VDD`, `VSS`

#### OR2 做缓冲

OR2 的一个输入接 CLA4 的 COUT_INT，另一个输入接 VSS → `COUT_INT OR 0 = COUT_INT`，作用是驱动外部负载。

### 第二十步: CMP_GE 比较器

比较两个 4 位数 A 和 B，输出 GE=1 当且仅当 A ≥ B。

#### 逻辑

```
GE = (A > B) OR (A == B)

A > B: 从最高位到最低位逐位比
  位3: GT3 = A3 & ~B3
  位2: GT2 = EQ3 & (A2 & ~B2)   ← 需要位3相等才比位2
  位1: GT1 = EQ3 & EQ2 & (A1 & ~B1)
  位0: GT0 = EQ3 & EQ2 & EQ1 & (A0 & ~B0)

A == B: EQ[3:0] 全为 1
  EQ[i] = ~(A[i] XOR B[i])
```

#### 接线表

**第 1 段: 位相等检测 (4 XOR2 + 4 INV)**

| Cell | 输入 | 输出 | 说明 |
|:---|:---|:---|:---|
| XOR_EQ3 | A3, B3 | X3 | A3 XOR B3 (使用第九步的 XOR2 单元) |
| INV_EQ3 | X3 | EQ3 | EQ3 = ~(A3 XOR B3), 即 A3 与 B3 相等 |
| XOR_EQ2 | A2, B2 | X2 | |
| INV_EQ2 | X2 | EQ2 | |
| XOR_EQ1 | A1, B1 | X1 | |
| INV_EQ1 | X1 | EQ1 | |
| XOR_EQ0 | A0, B0 | X0 | |
| INV_EQ0 | X0 | EQ0 | |

**第 2 段: A > B 逐位比较**

| Cell | 输入 | 输出 | 说明 |
|:---|:---|:---|:---|
| INV_B3 | B3 | B3_N | ~B3 |
| AND_GT3 | A3, B3_N | GT3 | A3 & ~B3 |
| INV_B2 | B2 | B2_N | ~B2 |
| AND_GT2_RAW | A2, B2_N | GT2_RAW | A2 & ~B2 |
| AND_GT2 | EQ3, GT2_RAW | GT2 | EQ3 成立时 GT2 才有效 |
| INV_B1 | B1 | B1_N | |
| AND_GT1_RAW | A1, B1_N | GT1_RAW | |
| AND_EQ32 | EQ3, EQ2 | EQ32 | EQ3 & EQ2 |
| AND_GT1 | EQ32, GT1_RAW | GT1 | |
| INV_B0 | B0 | B0_N | |
| AND_GT0_RAW | A0, B0_N | GT0_RAW | |
| AND_EQ321 | EQ32, EQ1 | EQ321 | EQ3 & EQ2 & EQ1 |
| AND_GT0 | EQ321, GT0_RAW | GT0 | |

**第 3 段: OR 汇总**

| Cell | 输入 | 输出 |
|:---|:---|:---|
| OR_GT_A | GT3, GT2 | GT_TMP1 |
| OR_GT_B | GT_TMP1, GT1 | GT_TMP2 |
| OR_GT_C | GT_TMP2, GT0 | A_GT_B |
| AND_EQ_ALL | EQ3, EQ2 | EQ_TMP1 |
| AND_EQ_A | EQ_TMP1, EQ1 | EQ_TMP2 |
| AND_EQ_B | EQ_TMP2, EQ0 | A_EQ_B |
| OR_GE | A_GT_B, A_EQ_B | GE |

#### 打 Pin

`A3`, `A2`, `A1`, `A0`, `B3`, `B2`, `B1`, `B0`, `GE`, `VDD`, `VSS`

#### 参考 SPICE

对照 `cadence_netlists_smic18/03_snn_neuron.sp` 中的 `CMP_GE` 子电路逐段连线。

### 第二十一步: SYNC_RESET (同步复位脉冲整形)

把比较器的组合逻辑 SPIKE_RAW 延迟一拍，同步到时钟域。

1. 新建 cell `SYNC_RESET`
2. Instance 1 个 `DFF`
3. 接线:

| 线 | 起点 | 终点 |
|:---|:---|:---|
| SPIKE_RAW | 外部 pin `SPIKE_RAW` | DFF.D |
| CLK | 外部 pin `CLK` | DFF.CLK |
| CLR_SYNC | DFF.Q | 外部 pin `CLR_SYNC` |
| (不用) | DFF.Q_N | (悬空) |

4. 打 Pin: `SPIKE_RAW`, `CLK`, `CLR_SYNC`, `VDD`, `VSS`

**原理**: DFF 在 CLK↑ 时采样 SPIKE_RAW → Q=SPIKE_RAW。所以 CLR_SYNC 比 SPIKE_RAW 落后一个时钟周期，下一个 CLK↑ 才去清零积分器。

### 第二十二步: MUX4 (4 位 2-选-1)

= 4 个 MUX2to1 + 4 个 INV 输出缓冲。通用多路选择器，每个位独立从 D0[i] 和 D1[i] 中二选一。

1. 新建 cell `MUX4`
2. Instance 4 个 `MUX2to1`, 4 个 `INV`
3. 接线:

| 位 | MUX2to1 实例 | D0 | D1 | SEL | 输出→INV→ |
|:---|:---|:---|:---|:---|:---|
| 0 | XMUX0 | D00 | D10 | SEL | → INV0 → Y0 |
| 1 | XMUX1 | D01 | D11 | SEL | → INV1 → Y1 |
| 2 | XMUX2 | D02 | D12 | SEL | → INV2 → Y2 |
| 3 | XMUX3 | D03 | D13 | SEL | → INV3 → Y3 |

   即：
   - 4 个 MUX2to1 的 SEL 都接同一个外部 pin `SEL`
   - 每路 MUX2to1 输出各接 1 个 INV → Y[i]（MUX2to1 输出需要反相恢复）
   - D0[3:0] 和 D1[3:0] 均为外部输入，不硬编码 VSS

4. 打 Pin: `D03`, `D02`, `D01`, `D00`, `D13`, `D12`, `D11`, `D10`, `SEL`, `Y3`, `Y2`, `Y1`, `Y0`, `VDD`, `VSS`

**在 IF_INTEGRATOR 中使用时**: D0[3:0]=W[3:0], D1[3:0]=VSS。此时 SPIKE=0 → 选 W (加权重)，SPIKE=1 → 选 VSS=0 (不加权重)。

> **MUX4 输出极性**: MUX4 每路输出经 INV 反相，因此 Y = ~(选中输入)。该 INV 在 IF_INTEGRATOR→ADD4 链路中自然补偿（ADD4 的 FA 内部无极性依赖），功能无影响。

### 第二十三步: IF_INTEGRATOR (IF 积分器)

= MUX4 + ADD4 + REG4。每个 CLK↑ 把 MUX 的输出加到膜电位上。

#### 功能

```
每个时间步:
  MUX4: SPIKE=0 → I = W (有脉冲则注入权重); SPIKE=1 → I = 0 (无脉冲)
  ADD4: V_new = V_old + I
  REG4: CLK↑ 时存入 V_new, 同时 V_new 反馈回 ADD4.B 作为下一周期 V_old
```

> **注意**: SPIKE 信号来自 IF_NEURON_FULL 外部的 `SPIKE_IN`。在本 cell 内部统一叫 `SPIKE`。

#### 子电路端口顺序

在实例化前必须确认每个子 cell 的引脚顺序：

| 子 cell | 端口顺序 |
|---|---|
| `MUX4` | D03 D02 D01 D00 D13 D12 D11 D10 SEL Y3 Y2 Y1 Y0 |
| `ADD4` | A3 A2 A1 A0 B3 B2 B1 B0 CIN S3 S2 S1 S0 COUT |
| `REG4` | D3 D2 D1 D0 CLK CLR Q3 Q2 Q1 Q0 |

#### 实例化接线

```
* MUX4: 权重 W[3:0] 接 D0 端口, VSS=0 接 D1 端口
* SEL=0 → D0 路导通 → I = W; SEL=1 → D1 路导通 → I = 0
XMUX: W3 W2 W1 W0 VSS VSS VSS VSS SPIKE I3 I2 I1 I0 MUX4

* ADD4: A = MUX4 输出 I (突触电流), B = 寄存器反馈 V (上周期膜电位)
XADD: I3 I2 I1 I0 V3 V2 V1 V0 VSS S3 S2 S1 S0 COUT_S DISCARD  ADD4
       ↑               ↑               ↑   ↑               ↑
       突触电流I        反馈膜电位V_old   进位输入=0    进位输出(不用)

* REG4: D = ADD4 求和结果 S, CLK=CLK, CLR=CLR
XREG: S3 S2 S1 S0 CLK CLR V3 V2 V1 V0 REG4
       ↑               ↑   ↑    V 同时输出到外部 pin
       新膜电位V_new       清零
```

#### 接线表

| 线标 | 起点 | 终点 | 说明 |
|:---|:---|:---|:---|
| W[3:0] | 外部 pin `W3/W2/W1/W0` | MUX4.D00~D03 | 突触权重(4位) |
| VSS → D1 | VSS | MUX4.D10~D13 | D1 端口全接 0 |
| SPIKE | 外部 pin `SPIKE` | MUX4.SEL | 脉冲输入控制选通 |
| I[3:0] | MUX4.Y0~Y3 | 内部 label `I3/I2/I1/I0` → ADD4.A[3:0] | 选通的权重 |
| V_fb[3:0] | REG4.Q[3:0] → 外部 pin `V3/V2/V1/V0` | ADD4.B[3:0] (同一根线分叉) | 反馈膜电位 |
| ADD4.CIN | VSS | ADD4.CIN | 进位输入恒为 0 |
| S[3:0] | ADD4.S[3:0] | REG4.D[3:0] | 新膜电位 → 寄存器输入 |
| ADD4.COUT | ADD4.COUT | 悬空 (label `COUT_DISCARD`) | 进位不用 |
| CLK | 外部 pin `CLK` | REG4.CLK | 时钟 |
| CLR | 外部 pin `CLR` | REG4.CLR | 清零(来自上层组合复位) |
| V[3:0] | REG4.Q[3:0] | 外部 pin `V3/V2/V1/V0` | 膜电位,同时反馈回 ADD4.B |
| VDD | VDD | 所有子 cell 的 VDD | |
| VSS | VSS | 所有子 cell 的 VSS 及 ADD4.CIN | |

#### 反馈环关键点

`REG4.Q[3:0]` 这根线**同时**连到两处：
- 外部 pin `V[3:0]`（输出膜电位）
- `ADD4.B[3:0]`（作为下周期的累加基数）

这就是闭合的积分反馈环路。画线时别只引出到 pin 就停，要确认 ADD4.B 也接到了。

#### 打 Pin

`W3`, `W2`, `W1`, `W0`, `SPIKE`, `CLK`, `CLR`, `V3`, `V2`, `V1`, `V0`, `VDD`, `VSS`

共 12 个 pin，不引出内部 label `I[3:0]`, `S[3:0]`, `COUT_DISCARD`。

### 第二十四步: IF_NEURON_FULL 顶层 (带同步复位, 推荐直接搭建)

> **说明**: SPICE 中还有一个 `IF_NEURON` 版本（无同步复位, SPIKE 用完就立即清零）。本指南**跳过** `IF_NEURON`，直接搭 `IF_NEURON_FULL`，因为同步复位是正确实现 SNN 时序要求的唯一方案。`IF_NEURON` 仅供理解对比，不需要建 cell。

#### IF_NEURON_FULL 接线表

1. 新建 cell `IF_NEURON_FULL`
2. Instance 1 个 `IF_INTEGRATOR`, 1 个 `CMP_GE`, 1 个 `SYNC_RESET`, 2 个 `OR2`

#### 接线表

| 标号 | 子电路 | 连线 | 说明 |
|:---|:---|:---|:---|
| 1 | `IF_INTEGRATOR` | W=外部 pin `W[3:0]`, SPIKE=外部 pin `SPIKE_IN`, CLK=外部 pin `CLK`, CLR=内部 label `CLR_COMB` → V=内部 label `V[3:0]` | 积分器 |
| 2 | `CMP_GE` | A=`V[3:0]`, B=外部 pin `VTH[3:0]` → GE=内部 label `SPIKE_RAW` | 比较膜电位 ≥ 阈值 |
| 3 | `SYNC_RESET` | SPIKE_RAW=`SPIKE_RAW`, CLK=外部 pin `CLK` → CLR_SYNC=内部 label `CLR_SYNC` | 同步延迟一拍 |
| 4 | `OR2_CLR` | A=外部 pin `CLR`, B=`CLR_SYNC` → OUT=`CLR_COMB` | 合并外部复位与自复位 |
| 5 | `OR2_BUF` | A=`SPIKE_RAW`, B=VSS → OUT=外部 pin `SPIKE_OUT` | 缓冲输出 |

> **V[3:0] 的分叉**：`V[3:0]` 这根线从 IF_INTEGRATOR 的 V 端口出来后同时连到三处：
> - `CMP_GE.A[3:0]`（比较阈值）
> - **外部 pin `V3/V2/V1/V0`**（输出膜电位供观测/仿真）
> - IF_INTEGRATOR 内部 `ADD4.B[3:0]`（加法反馈，已在内层接好）

> **命名区分**：
> - `SPIKE_IN`（外部 pin）≠ `SPIKE`（IF_INTEGRATOR 内部）
> - `SPIKE_RAW`（CMP_GE 比较结果）≠ `SPIKE_OUT`（缓冲输出）
> - `CLR`（外部 pin）≠ `CLR_SYNC`（同步延迟）≠ `CLR_COMB`（合并后送入积分器）

#### 反馈环路

```
                              ┌──→ 外部 pin V3/V2/V1/V0 (输出膜电位)
                              │
SPIKE_IN ─→ IF_INTEGRATOR ─ V[3:0] ─┬──→ CMP_GE.A (比较阈值)
                              │      │
                              │      ↓
                              │    CMP_GE ─ SPIKE_RAW ─┬──→ OR2_BUF ─→ SPIKE_OUT (脉冲输出)
                              │                         │
                              │                         └──→ SYNC_RESET ─ CLR_SYNC
                              │                                    │
                              │                          ┌─────────┘
                              │                          ↓
           IF_INTEGRATOR.CLR ←── CLR_COMB ←── OR2_CLR ←── CLR (外部)
```

环路说明：
1. **膜电位反馈**：`V[3:0]` 从 IF_INTEGRATOR 输出 → 进 CMP_GE.A 比较阈值，**同时引出到外部 pin `V3/V2/V1/V0`**（IF_INTEGRATOR 内部还有一路反馈到 ADD4.B，已在内层接好，不在此层重复）
2. **比较触发**：V ≥ Vth → `SPIKE_RAW = 1`（组合逻辑, 立即）
3. **同步延迟**：SPIKE_RAW → DFF.CLK↑ → `CLR_SYNC = 1`（落后 CLK 一拍）
4. **复位合并**：`CLR_COMB = CLR | CLR_SYNC`（OR2, 外部复位 OR 自复位）
5. **清零积分器**：CLR_COMB → REG4.CLR → 下一 CLK↑ 膜电位归零

#### SPIKE_RAW 的两条并行路径

```
SPIKE_RAW ─┬──→ OR2_BUF ─→ SPIKE_OUT (立即, 当前 CLK↑ 就有脉冲出来)
           │
           └──→ DFF ─ CLR_SYNC → OR2_CLR → IF_INTEGRATOR.CLR → REG4.CLR (延迟一拍清零)
```

> 所以 SPIKE_OUT 在**当拍**就有效脉冲, 但清零在**下一拍**才发生。这保证了 SPIKE_OUT 有完整的时钟宽度供外部读取。

#### 打 Pin

| Pin 名 | Direction | 位宽 | 说明 |
|:---|:---:|:---|:---|
| `W3/W2/W1/W0` | input | 4 | 突触权重 |
| `SPIKE_IN` | input | 1 | 脉冲输入 |
| `CLK` | input | 1 | 时钟 |
| `CLR` | input | 1 | 外部复位 |
| `VTH3/VTH2/VTH1/VTH0` | input | 4 | 阈值电压 |
| `V3/V2/V1/V0` | output | 4 | 膜电位输出 |
| `SPIKE_OUT` | output | 1 | 脉冲输出 (1bit 正逻辑: V>=Vth → 1) |
| `VDD` | inputOutput | — | 电源 |
| `VSS` | inputOutput | — | 地 |

**共 16 个 pin**。内部 label (不引 pin)：`SPIKE_RAW`, `CLR_SYNC`, `CLR_COMB`。

#### 参考 SPICE

对照 `cadence_netlists_smic18/03_snn_neuron.sp` 中 `IF_NEURON_FULL` 子电路 (行 238-256)。

---

## 验证策略: 每画一级仿真一级

**不要等画完 MAC 再仿真**。每画完一个 cell 就建 testbench 跑一次。

### Testbench 通用模板

每个 testbench 的基本结构都是一样的，学会 INV 的 testbench，后面 23 个都一样搭：

```
TB_XXX schematic 中必须有的:
  - 被测 cell 的 symbol instance (1 个)
  - VDD!/gnd! pin (inputOutput) ← 供电
  - vdc (1.8V) 正极→VDD! pin, 负极→gnd! pin
  - vpulse/vdc 作输入激励
  - 输出 pin (output) ← 观察波形
  - 所有电压源负极 → gnd! pin

创建 testbench 的标准步骤:
  1. Library Manager → 选中 SNN_PROJECT
  2. File → New → Cell View
  3. Cell Name: TB_XXX, View: schematic, Tool: Composer-Schematic
  4. 按下面的接线表放置 instance、pin、电压源
  5. F8 (Check and Save)
  6. ADE L → Setup → Model Libraries → 选 smic18mmrf 的 .scs/.lib 文件
  7. Analyses → Choose → tran → Stop Time (见下表)
  8. Outputs → To Be Plotted → 选需要观察的 net
  9. Simulation → Netlist and Run (或绿色播放键)
```

### vpulse 参数速查表

每个用到 vpulse 的 testbench 都按以下参数配置 (Instance 放 `vpulse` 来自 `analogLib`):

| 参数 | 典型值 | 说明 |
|:---|:---|:---|
| Voltage 1 | 0 V | 起始/低电平电压 |
| Voltage 2 | 1.8 V | 脉冲高电平电压 (=VDD) |
| Delay time | 0 s | 延迟多久开始发脉冲 |
| Rise time | 100p | 上升沿时间 (0 会导致收敛问题) |
| Fall time | 100p | 下降沿时间 |
| Pulse width | 5u | 高电平持续时间 |
| Period | 10u | 脉冲周期 |

> **调整 Pulse width / Period**：不同 testbench 需要的时钟/信号周期不同，具体见下面每个 testbench 的说明。

### vdc 参数

| 参数 | 值 |
|:---|:---|
| DC voltage | 1.8V (供电); 或 0V (用作逻辑 0); 或具体值用于多 bit 输入|

---

### 第 1 轮: 纯晶体管级 (验证底层工艺可用)

---

#### TB_INV (已完成, 此处作参考模板)

**被测 cell**: `INV` (IN→OUT, 1.8V 供电)

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| IN 激励 | vpulse: V1=0, V2=1.8V, period=10u, pulse width=5u, rise/fall=100p。+极→IN pin + INV.IN, −极→gnd! pin |
| OUT 观测 | output pin `OUT` 连到 INV.OUT |

**仿真设置**:
- Stop Time: 20u (2 个周期, 看到翻转)
- 观测: IN (vpulse 波形) + OUT (反相结果)

**验证标准**: IN=VDD 时 OUT=0; IN=0 时 OUT=VDD。

---

#### TB_TG

**被测 cell**: `TG` (IN→OUT, C/C_N 控制通断)

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| IN | vdc (1.8V), +→TG.IN + input pin `IN`, −→gnd! pin |
| C (控制) | vpulse: V1=0, V2=1.8V, period=10u, pulse width=5u, rise/fall=100p。+→TG.C + input pin `C`, −→gnd! pin |
| C_N (反相控制) | vpulse: V1=1.8V, V2=0, period=10u, pulse width=5u, rise/fall=100p (与 C 反相)。+→TG.C_N + input pin `C_N`, −→gnd! pin |
| OUT | output pin `OUT` 连 TG.OUT |

**仿真设置**:
- Stop Time: 20u
- 观测: C + OUT (TG 通断)

**验证标准**: C=1.8V(C_N=0)时 OUT=1.8V(导通); C=0(C_N=1.8V)时 OUT=高阻(悬空)。

---

#### TB_NAND2

**被测 cell**: `NAND2` (A,B→OUT)

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| A | vpulse: V1=0, V2=1.8V, period=20u, pulse width=10u。+→A pin + NAND2.A, −→gnd! pin |
| B | vpulse: V1=0, V2=1.8V, period=10u, pulse width=5u。+→B pin + NAND2.B, −→gnd! pin |
| OUT | output pin `OUT` 连 NAND2.OUT |

**仿真设置**:
- Stop Time: 20u (覆盖所有 4 种组合)
- 观测: A + B + OUT

**波形解读**:
```
时间   A    B    OUT
0-5u   0    0    1
5-10u  0    1    1
10-15u 1    0    1
15-20u 1    1    0
```

---

#### TB_NOR2

**被测 cell**: `NOR2` (A,B→OUT)

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| A | vpulse: V1=0, V2=1.8V, period=20u, pulse width=10u。+→A pin, −→gnd! pin |
| B | vpulse: V1=0, V2=1.8V, period=10u, pulse width=5u。+→B pin, −→gnd! pin |
| OUT | output pin `OUT` 连 NOR2.OUT |

**仿真设置**:
- Stop Time: 20u
- 观测: A + B + OUT

**波形解读**: 00→1, 01→0, 10→0, 11→0。

---

### 第 2 轮: 基本逻辑门

---

#### TB_AND2

**被测 cell**: `AND2` (A,B→OUT)

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| A | vpulse: V1=0, V2=1.8V, period=20u, pulse width=10u。+→A pin, −→gnd! pin |
| B | vpulse: V1=0, V2=1.8V, period=10u, pulse width=5u。+→B pin, −→gnd! pin |
| OUT | output pin `OUT` 连 AND2.OUT |

**仿真设置**: Stop Time=20u, 观测 A+B+OUT。

**波形解读**: 00→0, 01→0, 10→0, 11→1。

---

#### TB_OR2

**被测 cell**: `OR2` (A,B→OUT)

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| A | vpulse: V1=0, V2=1.8V, period=20u, pulse width=10u。+→A pin, −→gnd! pin |
| B | vpulse: V1=0, V2=1.8V, period=10u, pulse width=5u。+→B pin, −→gnd! pin |
| OUT | output pin `OUT` 连 OR2.OUT |

**仿真设置**: Stop Time=20u, 观测 A+B+OUT。

**波形解读**: 00→0, 01→1, 10→1, 11→1。

---

#### TB_XNOR2

**被测 cell**: `XNOR2` (A,B→OUT, A⊙B)

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| A | vpulse: V1=0, V2=1.8V, period=20u, pulse width=10u。+→A pin, −→gnd! pin |
| B | vpulse: V1=0, V2=1.8V, period=10u, pulse width=5u。+→B pin, −→gnd! pin |
| OUT | output pin `OUT` 连 XNOR2.OUT |

**仿真设置**: Stop Time=20u, 观测 A+B+OUT。

**波形解读**: 00→1, 01→0, 10→0, 11→1 (同或: 相同时输出 1)。

---

#### TB_XOR2

**被测 cell**: `XOR2` (A,B→OUT, A⊕B)

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| A | vpulse: V1=0, V2=1.8V, period=20u, pulse width=10u。+→A pin, −→gnd! pin |
| B | vpulse: V1=0, V2=1.8V, period=10u, pulse width=5u。+→B pin, −→gnd! pin |
| OUT | output pin `OUT` 连 XOR2.OUT |

**仿真设置**: Stop Time=20u, 观测 A+B+OUT。

**波形解读**: 00→0, 01→1, 10→1, 11→0 (异或: 不同时输出 1)。

---

#### TB_MUX2to1

**被测 cell**: `MUX2to1_CORRECT` (D0,D1,SEL→Y)

**激励设计**: D0 接 VDD(逻辑 1), D1 接 VSS(逻辑 0)。SEL=0→Y=1, SEL=1→Y=0。

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| D0 | vdc (1.8V) +→D0 pin + MUX.D0, −→gnd! pin |
| D1 | vdc (0V) +→D1 pin + MUX.D1, −→gnd! pin |
| SEL | vpulse: V1=0, V2=1.8V, period=10u, pulse width=5u。+→SEL pin, −→gnd! pin |
| Y | output pin `Y` 连 MUX.Y |

**仿真设置**: Stop Time=20u, 观测 SEL+Y。

**验证标准**: SEL=0→Y=1(选 D0)=VDD; SEL=1→Y=0(选 D1)=VSS。

---

#### TB_DFF

**被测 cell**: `DFF` (D,CLK→Q,Q_N)

**激励设计**: D 用 20u 周期方波, CLK 用 5u 周期时钟。在每个 CLK↑ 瞬间观测 Q 是否跟随 D。

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| D | vpulse: V1=0, V2=1.8V, period=20u, pulse width=10u, rise/fall=100p。+→D pin, −→gnd! pin |
| CLK | vpulse: V1=0, V2=1.8V, period=4u, pulse width=2u, rise/fall=100p。+→CLK pin, −→gnd! pin |
| Q | output pin `Q` 连 DFF.Q |
| Q_N | output pin `Q_N` 连 DFF.Q_N |

> **CLK 时序要求**: CLK 周期必须是 D 周期的 1/5 左右，才能在 CLK↑ 沿清晰采到 D 的变化。

**仿真设置**:
- Stop Time: 20u
- 观测: CLK + D + Q + Q_N

**验证标准**:
- CLK↑ 瞬间, Q = D 的值
- 两个 CLK↑ 之间, Q 保持不变 (锁存)
- Q_N 始终是 Q 的反相

---

#### TB_DFF_CLR

**被测 cell**: `DFF_CLR` (D,CLK,CLR→Q,Q_N)

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| D | vdc (1.8V) +→D pin, −→gnd! pin (始终为 1) |
| CLK | vpulse: V1=0, V2=1.8V, period=4u, pulse width=2u。+→CLK pin, −→gnd! pin |
| CLR | vpulse: V1=0, V2=1.8V, delay=12u, period=20u, pulse width=4u。+→CLR pin, −→gnd! pin |
| Q | output pin `Q` |
| Q_N | output pin `Q_N` |

**仿真设置**: Stop Time=20u, 观测 CLK+CLR+D+Q。

**验证标准**:
- 0-12u: CLR=0, D=1 → 每 CLK↑ Q=1 (正常工作)
- 12-16u: CLR=1 → 下一 CLK↑ Q=0 (清零生效)
- 16-20u: CLR=0 → 下一 CLK↑ Q=1 (恢复)

---

### 第 3 轮: 算术单元

---

#### TB_HA

**被测 cell**: `HA` (A,B→SUM,COUT)

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| A | vpulse: V1=0, V2=1.8V, period=20u, pulse width=10u。+→A pin, −→gnd! pin |
| B | vpulse: V1=0, V2=1.8V, period=10u, pulse width=5u。+→B pin, −→gnd! pin |
| SUM | output pin `SUM` |
| COUT | output pin `COUT` |

**仿真设置**: Stop Time=20u, 观测 A+B+SUM+COUT。

**波形解读**:
```
A B | SUM COUT   (SUM=A⊕B, COUT=A·B)
0 0 |  0   0
0 1 |  1   0
1 0 |  1   0
1 1 |  0   1
```

---

#### TB_FA

**被测 cell**: `FA` (A,B,CIN→SUM,COUT)

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| A | vpulse: V1=0, V2=1.8V, period=40u, pulse width=20u。+→A pin, −→gnd! pin |
| B | vpulse: V1=0, V2=1.8V, period=20u, pulse width=10u。+→B pin, −→gnd! pin |
| CIN | vpulse: V1=0, V2=1.8V, period=10u, pulse width=5u。+→CIN pin, −→gnd! pin |
| SUM | output pin `SUM` |
| COUT | output pin `COUT` |

**仿真设置**: Stop Time=40u, 观测 A+B+CIN+SUM+COUT。

**波形解读**: 三个输入按不同周期组合，共 8 种组合：SUM=A⊕B⊕CIN, COUT=(A·B)|(CIN·(A⊕B))。

---

#### TB_REG4

**被测 cell**: `REG4` (D[3:0],CLK,CLR→Q[3:0])

**激励设计**: 给 4 位输入赋固定值，CLK↑ 时锁存。

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| D3 | vdc (1.8V) +→D3 pin, −→gnd! pin (= 二进制 1) |
| D2 | vdc (0V) +→D2 pin, −→gnd! pin (= 0) |
| D1 | vdc (1.8V) +→D1 pin, −→gnd! pin (= 1) |
| D0 | vdc (0V) +→D0 pin, −→gnd! pin (= 0) |
| CLK | vpulse: V1=0, V2=1.8V, period=4u, pulse width=2u。+→CLK pin, −→gnd! pin |
| CLR | vpulse: V1=0, V2=1.8V, delay=12u, period=20u, pulse width=4u。+→CLR pin, −→gnd! pin |
| Q3/Q2/Q1/Q0 | output pin 各一个 |

> D[3:0] = 1010 (二进制 10)。用固定 vdc 做 4 位输入。

**仿真设置**: Stop Time=20u, 观测 CLK+CLR+Q3+Q2+Q1+Q0。

**验证标准**:
- CLK↑→Q[3:0]=1010 (锁存 D 的值)
- CLR=1→下一 CLK↑ Q[3:0]=0000 (清零)
- CLR=0→下一 CLK↑ Q[3:0]=1010 (恢复锁存)

---

#### TB_ADD4

**被测 cell**: `ADD4` (A[3:0],B[3:0],CIN→S[3:0],COUT)

**激励设计**: 做 3+5=8。A=0011(3), B=0101(5), CIN=0。观测 S=1000(8), COUT=0。

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| A3/A2/A1/A0 | vdc: A3=0V, A2=0V, A1=1.8V, A0=1.8V (0011 = 3) |
| B3/B2/B1/B0 | vdc: B3=0V, B2=1.8V, B1=0V, B0=1.8V (0101 = 5) |
| CIN | vdc (0V) +→CIN pin, −→gnd! pin |
| S3/S2/S1/S0 | output pin 各一个 |
| COUT | output pin `COUT` |

**仿真设置**: Stop Time=1u (纯组合逻辑, 无时钟, 短仿真即可), 观测 S[3:0]+COUT。

**验证标准**: S[3:0]=1000 (S3=1.8V, S2=S1=S0=0V), COUT=0V。

> **多测一组**: 改 A=0111(7), B=1001(9)→S=0000, COUT=1 (7+9=16, 4bit 溢出)。

---

#### TB_CLA4

**被测 cell**: `CLA4` (A[3:0],B[3:0],CIN→S[3:0],COUT)

**接线和激励与 TB_ADD4 完全相同**（CLA4 和 ADD4 功能一样，只是进位计算方式不同）。

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| A3/A2/A1/A0 | vdc: 0011 (3) 或 0111 (7) |
| B3/B2/B1/B0 | vdc: 0101 (5) 或 1001 (9) |
| CIN | vdc (0V) |
| S3/S2/S1/S0 | output pin |
| COUT | output pin `COUT` |

**验证标准**: 和 ADD4 结果一致。CLA4 优势是延迟更小(进位并行计算)，功能验证结果相同。

---

### 第 4 轮: 复杂系统

---

#### TB_ARRAY_MULT_4X4

**被测 cell**: `ARRAY_MULT_4X4` (A[3:0],B[3:0]→Y[7:0])

**激励设计**: 测 3×5=15。A=0011(3), B=0101(5)。期望 Y=0000_1111(15)。

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| A3/A2/A1/A0 | vdc: A3=0V, A2=0V, A1=1.8V, A0=1.8V (0011 = 3) |
| B3/B2/B1/B0 | vdc: B3=0V, B2=1.8V, B1=0V, B0=1.8V (0101 = 5) |
| Y7/Y6/Y5/Y4/Y3/Y2/Y1/Y0 | output pin 各一个 |

**仿真设置**: Stop Time=2u (纯组合逻辑, 但规模大给多点时间), 观测 Y[7:0]。

**验证标准**: Y[7:0]=00001111 (Y7-Y4=0V, Y3=1.8V, Y2=1.8V, Y1=1.8V, Y0=1.8V) = 15。

> **再测一组**: A=0010(2), B=0111(7)→Y=00001110(14)。

---

#### TB_MAC

**被测 cell**: `MAC` (A[3:0],B[3:0],CLK,CLR→ACC[3:0],COUT)

**激励设计**: 演示累加 — 每个 CLK↑: ACC = ACC + A×B。A=3, B=5 (乘积=15)。CLR 先清零，再跑 3 个时钟周期: ACC 从 0→15→30(溢出 4bit=14+COUT)。

**搭建步骤（按操作顺序）**:

1. Library Manager → 选中 `WorkStation` → `File → New → Cell View` → Name: `TB_MAC`, View: `schematic`
2. 按 `i` → Browse → `WorkStation` → 选 `MAC` → 放 symbol 在画布中央
3. 按 `p` → 打 VDD! pin (Direction: **inputOutput**, Usage: **power**) 和 gnd! pin (Direction: **inputOutput**) → 放在上方和下方
   - **MAC symbol 的 VDD! 脚** 用 `w` 连线到 `VDD! pin`
   - **MAC symbol 的 gnd! 脚** 用 `w` 连线到 `gnd! pin`
4. 按 `i` → Browse → `analogLib` → 选 `vdc` → 放 10 个到画布上（1 个供电 + 9 个做输入常量）
   - **vdc0 (供电)**: DC voltage = `1.8`。正极→VDD! pin，负极→gnd! pin
   - **vdc_A0**: DC voltage = `1.8`。正极→MAC.A0，负极→gnd!
   - **vdc_A1**: DC voltage = `1.8`。正极→MAC.A1，负极→gnd!
   - **vdc_A2**: DC voltage = `0`。正极→MAC.A2，负极→gnd!
   - **vdc_A3**: DC voltage = `0`。正极→MAC.A3，负极→gnd!
   - **vdc_B0**: DC voltage = `1.8`。正极→MAC.B0，负极→gnd!
   - **vdc_B1**: DC voltage = `0`。正极→MAC.B1，负极→gnd!
   - **vdc_B2**: DC voltage = `1.8`。正极→MAC.B2，负极→gnd!
   - **vdc_B3**: DC voltage = `0`。正极→MAC.B3，负极→gnd!
   - 每个 vdc 的正极同时也是 input pin 的接入点，在对应的 vdc 正极连线上 **再打一个同名的 input pin**：
     - `p` → Name=`A0`, Direction=`input` → 放在 vdc_A0 正极到 MAC.A0 的连线上
     - `p` → Name=`A1`, Direction=`input` → 同理...
     - `p` → Name=`A2`, Direction=`input` → 同理...
     - `p` → Name=`A3`, Direction=`input` → 同理...
     - `p` → Name=`B0/B1/B2/B3`, Direction=`input` → 同理...
5. 按 `i` → Browse → `analogLib` → 选 `vpulse` → 放 2 个
   - **vpulse_CLK**: Voltage1=`0`, Voltage2=`1.8`, Period=`10u`, Pulse width=`5u`, Rise time=`100p`, Fall time=`100p`, Delay=`0`
     - 正极→MAC.CLK，负极→gnd!
     - 在正极连线上打 input pin `CLK`
   - **vpulse_CLR**: Voltage1=`0`, Voltage2=`1.8`, Period=`30u`, Pulse width=`5u`, Rise time=`100p`, Fall time=`100p`, Delay=`0`
     - 正极→MAC.CLR，负极→gnd!
     - 在正极连线上打 input pin `CLR`
6. 输出 pin（MAC symbol 的 ACC0/ACC1/ACC2/ACC3/COUT 各连一个 output pin）:
   - `p` → Name=`ACC0`, Direction=`output` → 放在 MAC.ACC0 的连线上
   - `p` → Name=`ACC1`, Direction=`output` → 同理
   - `p` → Name=`ACC2`, Direction=`output` → 同理
   - `p` → Name=`ACC3`, Direction=`output` → 同理
   - `p` → Name=`COUT`, Direction=`output` → 同理
7. **不要** 再放单独的 input pin 对 ACC0-3（它们是输出不是输入）
8. `F8` (Check and Save)

**最终 check 清单**:
- MAC symbol 的 VDD!/gnd! 都连到对应 pin
- 所有 vdc/vpulse 的负极都接到 gnd! pin
- A 的 4 个 vdc 分别为 A3=0/A2=0/A1=1.8V/A0=1.8V (二进制 0011 = 3)
- B 的 4 个 vdc 分别为 B3=0/B2=1.8V/B1=0/B0=1.8V (二进制 0101 = 5)
- CLK vpulse 连到 MAC.CLK, CLR vpulse 连到 MAC.CLR
- 5 个输出 ACC0-3 + COUT 都有 output pin

**仿真设置**:
- Stop Time: 30u
- ADE L → Analyses → tran → 30u
- Outputs → To Be Plotted: CLK, CLR, ACC0, ACC1, ACC2, ACC3, COUT
- 模型库: 和 TB_INV 一样，smic18mmrf 的 .scs 文件

**验证标准**:
- CLR 高电平后的第 1 个 CLK↑: ACC[3:0]=0000 (清零)
- 第 2 个 CLK↑: ACC = 0+15 = 1111 (15), COUT=0
- 第 3 个 CLK↑: ACC = 15+15 = 11110 (30) → ACC[3:0]=1110(14), COUT=1 (溢出)

---

#### TB_CMP_GE

**被测 cell**: `CMP_GE` (A[3:0],B[3:0]→GE)

**激励设计**: 设 B=3(0011) 固定。A 用不同值验证: A=5>3→GE=1, A=3=3→GE=1, A=1<3→GE=0。

由于 CMP_GE 是纯组合逻辑无时钟，用多个 vdc 组合一次跑完不行 (只能一组值)。简便方法：**手动改 A[3:0] 的 vdc 值跑三次**。

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| A3/A2/A1/A0 | vdc: 第一轮 0101(5); 第二轮 0011(3); 第三轮 0001(1) |
| B3/B2/B1/B0 | vdc: 0011(3) 固定 |
| GE | output pin |

**仿真设置**: Stop Time=1u (组合逻辑), 观测 GE。

**验证标准**:
| A | B | GE | 说明 |
|:--|:--|:---|:---|
| 5 (0101) | 3 (0011) | 1 | A > B |
| 3 (0011) | 3 (0011) | 1 | A = B (GE 含等于) |
| 1 (0001) | 3 (0011) | 0 | A < B |

> **如果想一次仿真看三种情况**: 可以把 A[3:0] 分别接不同周期的 vpulse（类似 TB_NAND2 的 A/B 错开周期），但对 4 位比较器会很复杂。分三次跑更简单直观。

---

#### TB_SYNC_RESET

**被测 cell**: `SYNC_RESET` (SPIKE_RAW,CLK→CLR_SYNC)

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| SPIKE_RAW | vpulse: V1=0, V2=1.8V, delay=10u, period=20u, pulse width=5u。+→SPIKE_RAW pin, −→gnd! pin |
| CLK | vpulse: V1=0, V2=1.8V, period=4u, pulse width=2u。+→CLK pin, −→gnd! pin |
| CLR_SYNC | output pin |

**仿真设置**: Stop Time=30u, 观测 CLK+SPIKE_RAW+CLR_SYNC。

**验证标准**: SPIKE_RAW=1 的**下一拍** CLK↑ 后 CLR_SYNC 才变 1。确认延迟一拍。

---

#### TB_MUX4

**被测 cell**: `MUX4` (D0[3:0],D1[3:0],SEL→Y[3:0])

**激励设计**: D0=0000(全 0), D1=0101(5)。SEL=0→Y=0, SEL=1→Y=5。

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| D03/D02/D01/D00 | vdc: 全 0V (0000) |
| D13/D12/D11/D10 | vdc: D13=0V, D12=1.8V, D11=0V, D10=1.8V (0101 = 5) |
| SEL | vpulse: V1=0, V2=1.8V, period=10u, pulse width=5u。+→SEL pin, −→gnd! pin |
| Y3/Y2/Y1/Y0 | output pin 各一个 |

**仿真设置**: Stop Time=20u, 观测 SEL+Y[3:0]。

**验证标准**: SEL=0→Y=0000; SEL=1→Y=0101(5)。

---

#### TB_IF_INTEGRATOR

**被测 cell**: `IF_INTEGRATOR` (W[3:0],SPIKE,CLK,CLR→V[3:0])

**激励设计**: W=3(0011), SPIKE 每 20u 来一次脉冲, CLK=4u 周期, CLR 开头清零。

期望: CLR 清零→V=0; 每次 SPIKE=1 且 CLK↑→V=V+W=0+3=3→6→9→...（溢出后回绕）。

| 连线 | 接法 |
|:---|:---|
| 供电 | vdc (1.8V) +→VDD! pin, −→gnd! pin |
| W3/W2/W1/W0 | vdc: W3=0V, W2=0V, W1=1.8V, W0=1.8V (0011 = 3) |
| SPIKE | vpulse: V1=0, V2=1.8V, delay=5u, period=20u, pulse width=5u。+→SPIKE pin, −→gnd! pin |
| CLK | vpulse: V1=0, V2=1.8V, period=4u, pulse width=2u。+→CLK pin, −→gnd! pin |
| CLR | vpulse: V1=0, V2=1.8V, delay=0, period=40u, pulse width=3u (开头清零)。+→CLR pin, −→gnd! pin |
| V3/V2/V1/V0 | output pin 各一个 |

**仿真设置**: Stop Time=40u, 观测 CLK+CLR+SPIKE+V[3:0]。

**验证标准**:
- CLR 清零后 V=0000
- 第 1 个 SPIKE 脉冲后的 CLK↑: V=0011(3)
- 第 2 个 SPIKE 脉冲后的 CLK↑: V=0110(6)
- 第 3 个 SPIKE 脉冲后的 CLK↑: V=1001(9)
- 没有 SPIKE 的周期: V 保持不变

---

#### TB_IF_NEURON_FULL

**被测 cell**: `IF_NEURON_FULL` (W[3:0],SPIKE_IN,CLK,CLR,VTH[3:0]→V[3:0],SPIKE_OUT)

**激励设计**: W=2(0010), VTH=5(0101), CLK=4u 周期, CLR=0(外部不复位, 靠内同步复位)。

期望: SPIKE_IN 脉冲→V 累加; V≥5→SPIKE_OUT=1; 下一拍 V 清零。

**搭建步骤（按操作顺序）**:

1. Library Manager → 选中 `WorkStation` → `File → New → Cell View` → Name: `TB_IF_NEURON_FULL`, View: `schematic`
2. 按 `i` → Browse → `WorkStation` → 选 `IF_NEURON_FULL` → 放 symbol 在画布中央
3. 按 `p` → 打 VDD! pin (Direction: **inputOutput**, Usage: **power**) 和 gnd! pin (Direction: **inputOutput**, Usage: **ground**) → 放在上方和下方
   - IF_NEURON_FULL symbol 的 **VDD! 脚** 用 `w` 连线到 `VDD! pin`
   - IF_NEURON_FULL symbol 的 **gnd! 脚** 用 `w` 连线到 `gnd! pin`
4. 按 `i` → Browse → `analogLib` → 选 `vdc` → 放 11 个
   - **vdc0 (供电)**: DC voltage = `1.8`。正极→VDD! pin，负极→gnd! pin
   - **vdc_W3**: DC voltage = `0` → 正极→W3, 负极→gnd! pin。在正极连线上打 input pin `W3`
   - **vdc_W2**: DC voltage = `0` → 正极→W2, 负极→gnd! pin。打 input pin `W2`
   - **vdc_W1**: DC voltage = `1.8` → 正极→W1, 负极→gnd! pin。打 input pin `W1`
   - **vdc_W0**: DC voltage = `0` → 正极→W0, 负极→gnd! pin。打 input pin `W0`
   - W = 二进制 0010 = 2
   - **vdc_CLR**: DC voltage = `0` → CLR pin（外部不复位）。正极→CLR pin，负极→gnd!
   - **vdc_VTH3**: DC voltage = `0` → VTH3 pin（VTH=0101=5: VTH3=0, VTH2=1, VTH1=0, VTH0=1）
   - **vdc_VTH2**: DC voltage = `1.8` → VTH2 pin
   - **vdc_VTH1**: DC voltage = `0` → VTH1 pin
   - **vdc_VTH0**: DC voltage = `1.8` → VTH0 pin
   - 每个 vdc 负极→gnd! pin，每个正极连线上打一个对应的 input pin
5. 按 `i` → Browse → `analogLib` → 选 `vpulse` → 放 2 个
   - **vpulse_CLK**: Voltage1=`0`, Voltage2=`1.8`, Period=`4u`, Pulse width=`2u`, Rise time=`100p`, Fall time=`100p`, Delay=`0`
     - 正极→CLK pin，负极→gnd!
   - **vpulse_SPIKE_IN**: Voltage1=`0`, Voltage2=`1.8`, Period=`10u`, Pulse width=`3u`, Rise time=`100p`, Fall time=`100p`, Delay=`5u`
     - 正极→SPIKE_IN pin，负极→gnd!
6. 输出 pin（IF_NEURON_FULL symbol 的 V0/V1/V2/V3/SPIKE_OUT 各连一个 output pin）
   - `p` → Name=`V0`, Direction=`output`
   - `p` → Name=`V1`, Direction=`output`
   - `p` → Name=`V2`, Direction=`output`
   - `p` → Name=`V3`, Direction=`output`
   - `p` → Name=`SPIKE_OUT`, Direction=`output`
7. `F8` (Check and Save)

**最终 check 清单**:
- IF_NEURON_FULL symbol 的 VDD!/gnd! 都连到对应 pin
- 所有 vdc/vpulse 的负极都接到 gnd! pin
- W 的 4 个 vdc: W3=0/W2=0/W1=1.8V/W0=0 (二进制 0010 = 2)
- VTH 的 4 个 vdc: VTH3=0/VTH2=1.8V/VTH1=0/VTH0=1.8V (二进制 0101 = 5)
- CLK vpulse 连到 CLK pin, SPIKE_IN vpulse 连到 SPIKE_IN pin
- CLR vdc=0V 连到 CLR pin（外部不复位，只靠内部同步复位）
- 5 个输出 V0-3 + SPIKE_OUT 都有 output pin

**仿真设置**:
- Stop Time: 40u
- ADE L → Analyses → tran → 40u
- Outputs → To Be Plotted: CLK, SPIKE_IN, V0, V1, V2, V3, SPIKE_OUT
- 模型库: 和 TB_INV 一样

**验证标准 (时序推理)**:
- 每来一个 SPIKE_IN=1: V 累加 2
- 第 1 个脉冲: V=0010(2) < VTH
- 第 2 个脉冲: V=0100(4) < VTH
- 第 3 个脉冲: V=0110(6) ≥ VTH(5) → SPIKE_OUT=1 (组合逻辑立即可见)
- SPIKE_OUT=1 后的下一个 CLK↑: V 被 CLR_SYNC 清零 → V=0000
- 后续脉冲重新累加...

**关键波形确认**: SPIKE_OUT=1 的当拍 V 还是 ≥VTH 的值，下一拍才归零。这就是同步复位的效果。

---

## 课题数据测量：功耗 & 延迟

验证波形正确后，需要从仿真中提取功耗和延迟数据用于课题对比分析。

### 测哪些 testbench

| Testbench | 测量目的 | 管数 |
|:---|:---|:---|
| **TB_INV** | 单门基准功耗/延迟 | 2 |
| **TB_MAC** | ANN 乘累加单元 (乘法器+加法器+寄存器) | ~916 |
| **TB_IF_NEURON_FULL** | SNN IF 脉冲神经元 (积分+比较+复位) | ~496 |

### 功耗测量步骤

1. 在 ADE L 跑完瞬态仿真后，确认波形正确
2. `Tools → Calculator`
3. 测量**平均功耗**：
   - 在 schematic 中点击 VDD! pin 上的红色连线（VDD 端口到 vdc 正极的那根线）
   - Calculator 窗口会自动出现该 net 的电压或电流路径
   - 在 Calculator 中函数选择 `average`，Signal 填 `IT("/V0/PLUS")`（即流过 1.8V vdc 的瞬态电流），点击 `Evaluate`
   - 也可以直接手输入：`average(IT("/V0/PLUS"))`
   - 结果乘以 1.8 = 平均功耗（W）
4. 测量**单次运算功耗**：
   - TB_MAC：用 `integ` 函数对一个 CLK 周期内的电流积分，再乘以 VDD，得到单次 MAC 能耗
   - TB_IF_NEURON_FULL：对一个完整的 SPIKE_IN 脉冲→累加→触发→清零周期的电流积分
5. 测量**静态功耗**：
   - 把 testbench 的所有 vpulse 改成 dc 0V（无信号翻转）
   - 跑瞬态仿真（Stop Time=1u 足够）
   - 用 Calculator `average(IT("/V0/PLUS"))` × 1.8V = 静态功耗

### 延迟测量步骤

1. 在 ADE L 波形窗口中，放大一个输入翻转沿到对应输出翻转沿的区间
2. Calculator → 函数选 `delay`
   - Signal1: 输入信号（如 CLK）
   - Signal2: 输出信号（如 ACC0）
   - Threshold Value1: 0.9V（50% VDD）
   - Threshold Value2: 0.9V
   - Edge Number1: `rising`（从 CLK↑ 算起）
   - Edge Number2: `rising` 或 `falling`（看输出在哪个沿变化）
   - 或直接用波形窗口里的 Marker：`Marker → Create Marker`，在输入和输出的 50%VDD 处各放一个，读 Δ 值
3. **TB_MAC** 测 CLK↑→ACC[3:0] 稳定输出的延迟（关键路径：乘法器 + CLA4 + REG4 setup）
4. **TB_IF_NEURON_FULL** 测 CLK↑→V[3:0] 稳定（积分器路径）和 CLK↑→SPIKE_OUT 稳定

### 数据记录模板

实测数据填入此表即可用于课题报告：

| 指标 | INV (基准) | MAC (ANN) | IF_NEURON_FULL (SNN) |
|:---|:---|:---|:---|
| 晶体管数 | 2 | ~916 | ~496 |
| 平均功耗 (W) | | | |
| 单次运算能耗 (J) | | | |
| 静态功耗 (W) | | | |
| 关键路径延迟 (s) | | | |
| 是否需乘法器 | 否 | 是 | 否 |
| 事件驱动 | 否 | 否 | 是 |

### IF_NEURON_FULL 脉冲稀疏度功耗模型

SNN 的功耗优势来自脉冲稀疏性——只有在 SPIKE_IN=1 时才发生运算。因此实际功耗不是恒定的：

- **活跃功耗** = 实测单次运算能耗 × 活跃频率（SPIKE_IN 脉冲频率）
- **空闲功耗** = 静态功耗（≈ SPIKE_IN=0 时只有漏电）
- **平均功耗** = 活跃功耗 × 脉冲稀疏度(%) + 空闲功耗 × (1 - 脉冲稀疏度)

结合软件侧的 SNN 仿真（你的 `snn_tradeoff.py`），可以知道不同时间步下的平均脉冲稀疏度，从而外推：
- 100 神经元层功耗 = 单神经元功耗 × 100
- 300 神经元功耗 = 单神经元功耗 × 300

---

## Virtuoso 快捷键速查

| 快捷键 | 作用 |
|:---|:---|
| `i` | Instance (放器件/subcell) |
| `w` | Wire (连线) |
| `p` | Pin (打引脚) |
| `l` | Label (标标签) |
| `c` | Copy (复制) |
| `m` | Move (移动) |
| `r` | Stretch (拉伸) |
| `k` | 标尺 |
| `F` | 全屏 |
| `Ctrl+A` | 全选 |
| `F8` | Check and Save |
| `Delete` | 删除 |

在有 subcell 的图中, 双击单元可以**下钻**进入内部 (`Shift+E` 回到上层)。

---

## 常见错误排查

| 现象 | 最可能的原因 |
|:---|:---|
| Check and Save 报 "unconnected pin" | 有 pin 没连, 检查所有 instance 引脚 |
| 仿真 INV 输出一直是 VDD | n18 的 bulk 没接 VSS |
| 仿真 TG 输出一直是高阻 | C 和 C_N 接反了 |
| DFF 不锁存 | 某个 TG 的 C/C_N 极性反了 |
| 加法器进位不对 | FA 里面 AND2 的输出接错 OR2 的输入 |
| 乘法器结果不对 | 检查部分积 AND2 的 4×4 阵列排列 |
| 比较器 A≥B 相反 | 检查 GT 链中 AND2 串的 EQ 信号顺序 |
| MAC 不累加 | CLA4 的 B 输入没接到 REG4 的反馈 |
| IF 积分器不积分 | MUX4 的 SEL 极性反了 |

---

## 总结: 你必须画的全部 cell

以构建顺序排列 (强烈建议按此顺序逐个创建, 前一个验证通过再画下一个):

```
 1. INV         ─ 放 1 n18 + 1 p18, 验证库能用
 2. TG          ─ 放 1 n18 + 1 p18, 源漏短接
 3. NAND2       ─ 2p并联 + 2n串联 (n串联W×2)
 4. NOR2        ─ 2p串联 + 2n并联 (p串联W×2)
 5. AND2        ─ NAND2 + INV
 6. OR2         ─ NOR2 + INV
 7. XNOR2       ─ 2TG + 3INV (传输门风格, 基础同或单元)
 8. XOR2        ─ XNOR2 + INV (真正异或)
 9. MUX2to1     ─ 2TG + INV
10. DFF         ─ 4TG + 7INV (最复杂, 耐心)
11. DFF_CLR     ─ DFF + AND2 (+1 INV 反相 CLR)
12. HA          ─ XOR2 + AND2
13. FA          ─ 2XOR2 + 2AND2 + OR2
14. REG4        ─ 4×DFF_CLR 拼线
15. ADD4        ─ 4×FA 串联
16. CLA4        ─ 24AND2 + 8XOR2 + 10OR2 (进位网30门)
17. ARRAY_MULT  ─ 18AND2 + 4HA + 8FA (含2缓冲AND2)
18. MAC         ─ ARRAY_MULT + CLA4 + REG4 + OR2缓冲
19. CMP_GE      ─ 4XOR2 + 8INV + 12AND2 + 4OR2 比较链
20. SYNC_RESET  ─ 1×DFF
21. MUX4        ─ 4×MUX2to1 + 4×INV
22. IF_INTEGR   ─ MUX4 + ADD4 + REG4
23. IF_NEURON   ─ IF_INTEGR + CMP_GE (无同步复位, SPICE中有但可跳过)
24. IF_NEURON_FULL ─ IF_INTEGR + CMP_GE + SYNC_RESET + OR2 (含同步复位, 直接实例化)
```

**共 24 个 cell**，按构建顺序，前一个验证通过再画下一个。
