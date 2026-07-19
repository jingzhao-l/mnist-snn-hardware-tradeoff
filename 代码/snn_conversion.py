"""
snn_conversion.py —— ANN-to-SNN 转换与脉冲神经网络核心实现
============================================================
功能：
  1. 加载已训练的 ANN 权重 (ann_mnist_weights_relu.npz)
  2. 权重归一化（max_norm / data_based 两种方法），
     使得 IF 神经元的脉冲发放率 ≈ ReLU(ANN 激活值)
  3. 泊松编码：将 MNIST 图片编码为泊松脉冲序列
  4. IF 神经元层 + 两层 SNN 网络（纯 numpy 手写）
  5. 在 MNIST 测试集上评估 SNN 准确率、脉冲稀疏率
  6. 保存 SNN 测试结果到文件

【ANN-to-SNN 转换的核心数学原理】
  IF 神经元经 T 步仿真后，其平均脉冲发放率 r 满足:
      r ≈ ReLU(W·r_in + b) / Vth
  因此，若将 ANN 权重按比例缩放，使 max_activation ≤ Vth，
  则 SNN 的脉冲发放率将与 ANN 的激活值成比例。
  最终分类时取脉冲计数最大的输出神经元，等价于 ANN 的 argmax。

所有代码纯 numpy 手写，注释中包含与硬件电路的对应关系。
"""

import numpy as np
import sys
import os
from sklearn.datasets import fetch_openml

# ============================================================
# 第 1 部分：可配置参数
# ============================================================

class SNNConfig:
    """SNN 所有可配置参数的集中管理

    参数说明：
    - T: 每张图片的仿真时间步数。类比：用多长的窗口观察神经元活动。
          T 越大 → 泊松编码的信息越完整 → 准确率越高 → 推理时间越长
    - Vth: IF 神经元的膜电位触发阈值。类比：神经元"兴奋"的灵敏度。
           Vth 越小 → 越容易触发 → 脉冲越多 → 功耗越高
    - norm_method: 权重归一化方法
      "max_norm"  — 除以每层权重的最大绝对值（简单快速，默认）
      "data_based" — 用训练集激活值的 99.9% 分位数（更精细，准确率较高）
    - percentile: data_based 归一化时的分位数（默认 99.9）
    - reset_mode: 触发后膜电位复位方式
      "hard" — 直接清零（硬件友好，本课题使用）
      "soft" — 减去阈值（保留余量，某些场景准确率更高，但电路复杂）
    """
    def __init__(self, T=50, Vth=1.0, norm_method="max_norm",
                 percentile=99.9, reset_mode="hard"):
        self.T = T
        self.Vth = Vth
        self.norm_method = norm_method
        self.percentile = percentile
        self.reset_mode = reset_mode

    def __repr__(self):
        return (f"SNNConfig(T={self.T}, Vth={self.Vth}, "
                f"norm='{self.norm_method}', percentile={self.percentile}, "
                f"reset='{self.reset_mode}')")


# ============================================================
# 第 2 部分：权重加载
# ============================================================

def load_ann_weights(weight_path):
    """从 .npz 文件加载已训练的 ANN 权重

    期望的键名（与 train_ann_relu.py 保存的格式一致）：
        W1  (784, 300)  输入层→隐藏层权重
        b1  (300,)       隐藏层偏置
        W2  (300, 10)    隐藏层→输出层权重
        b2  (10,)        输出层偏置

    Args:
        weight_path: .npz 文件路径

    Returns:
        (W1, b1, W2, b2) 四个 numpy 数组，转换为 float32
    """
    data = np.load(weight_path)
    W1 = data['W1'].astype(np.float32)
    b1 = data['b1'].astype(np.float32)
    W2 = data['W2'].astype(np.float32)
    b2 = data['b2'].astype(np.float32)
    print(f"[权重加载] 已从 {weight_path} 加载 ANN 权重")
    print(f"  W1: {W1.shape}, 范围 [{W1.min():.4f}, {W1.max():.4f}]")
    print(f"  b1: {b1.shape}, 范围 [{b1.min():.4f}, {b1.max():.4f}]")
    print(f"  W2: {W2.shape}, 范围 [{W2.min():.4f}, {W2.max():.4f}]")
    print(f"  b2: {b2.shape}, 范围 [{b2.min():.4f}, {b2.max():.4f}]")
    return W1, b1, W2, b2


# ============================================================
# 第 3 部分：权重归一化
# ============================================================

def max_norm_normalize(W1, b1, W2, b2):
    """最大绝对值归一化 (max-norm)

    【原理】
        将每层权重除以该层权重的最大绝对值。
        归一化后，任意单个输入脉冲对膜电位的最大贡献 ≤ 1.0。
        结合 Vth=1.0，神经元至少需要多个输入脉冲同时到达才能触发。
        这是最简单、最具硬件友好性的归一化方法。

    【与硬件电路的对应关系】
        归一化后权重 ∈ [-1, 1]，可用 8-bit 定点数精确表示，
        适合用 MUX + 加法器电路实现。

    Args:
        W1, b1: 第 1 层权重和偏置
        W2, b2: 第 2 层权重和偏置

    Returns:
        (W1_norm, b1_norm), (W2_norm, b2_norm)
    """
    # 第 1 层归一化：除以 |W1| 的最大值
    norm1 = max(np.max(np.abs(W1)), 1e-8)
    W1_norm = W1 / norm1
    b1_norm = b1 / norm1
    print(f"[max_norm] 第 1 层归一化因子: {norm1:.4f}")

    # 第 2 层归一化：除以 |W2| 的最大值
    norm2 = max(np.max(np.abs(W2)), 1e-8)
    W2_norm = W2 / norm2
    b2_norm = b2 / norm2
    print(f"[max_norm] 第 2 层归一化因子: {norm2:.4f}")

    return (W1_norm, b1_norm), (W2_norm, b2_norm)


def data_based_normalize(W1, b1, W2, b2, X_train, Vth=1.0, percentile=99.9,
                         max_samples=5000):
    """基于数据的归一化 (data-based normalization)

    【原理】
        利用训练集的激活值统计信息来缩放权重：
        1. 计算第 1 层 ANN 激活值 (ReLU)，取 99.9% 分位数 λ1
        2. 缩放 W1, b1 使激活值 ≤ Vth：scale1 = Vth/λ1
        3. 用归一化后的第 1 层重新计算激活值
        4. 计算第 2 层激活值的 99.9% 分位数 λ2
        5. 缩放 W2, b2：scale2 = Vth/λ2

    【为什么比 max_norm 更精确】
        max_norm 只看权重本身的分布，不看数据分布。
        数据驱动归一化根据实际输入信号的统计来调整，
        确保绝大多数神经元的膜电位不会超过阈值太多，
        从而更准确地匹配 ANN 的激活模式。
        通常在 T 较小时准确率提升明显（~2-5%）。

    【参考文献】
        Rueckauer et al., "Conversion of Continuous-Valued Deep Networks
        to Efficient Event-Driven Networks for Image Classification", 2017

    Args:
        W1, b1, W2, b2: 原始 ANN 权重
        X_train: 训练集图像 (n, 784), 值域 [0, 1]
        Vth: 目标阈值
        percentile: 分位数（默认 99.9）
        max_samples: 归一化使用的最大样本数（加速计算）

    Returns:
        (W1_norm, b1_norm), (W2_norm, b2_norm)
    """
    n_sample = min(max_samples, X_train.shape[0])
    X = X_train[:n_sample].astype(np.float32)
    print(f"[data_based] 使用 {n_sample} 张训练图片进行归一化 (分位数={percentile})")

    # ---- 第 1 层归一化 ----
    z1 = np.dot(X, W1) + b1          # (n_sample, 300)  — 仿射变换
    a1 = np.maximum(0, z1)           # (n_sample, 300)  — ReLU 激活
    max_act_l1 = np.percentile(a1, percentile)
    scale1 = Vth / max(max_act_l1, 1e-8)  # 防止除零
    W1_norm = W1 * scale1
    b1_norm = b1 * scale1
    print(f"[data_based] 第 1 层: λ={max_act_l1:.4f}, scale={scale1:.4f}")

    # ---- 第 2 层归一化（使用已归一化的第 1 层） ----
    z1_norm = np.dot(X, W1_norm) + b1_norm
    a1_norm = np.maximum(0, z1_norm)
    # 输出层在 SNN 中使用 IF 神经元（无 Softmax），
    # 其激活值应为 ReLU(z2)，因为 IF 神经元无法输出负的脉冲发放率
    z2 = np.dot(a1_norm, W2) + b2    # (n_sample, 10)
    a2 = np.maximum(0, z2)           # ReLU —— 对应 SNN 输出层的脉冲发放率
    max_act_l2 = np.percentile(a2, percentile)
    scale2 = Vth / max(max_act_l2, 1e-8)
    W2_norm = W2 * scale2
    b2_norm = b2 * scale2
    print(f"[data_based] 第 2 层: λ={max_act_l2:.4f}, scale={scale2:.4f}")

    return (W1_norm, b1_norm), (W2_norm, b2_norm)


# ============================================================
# 第 4 部分：泊松编码
# ============================================================

def poisson_encode(image_flat, T, seed=None):
    """将一张 MNIST 图片编码为泊松脉冲序列

    【原理】
        每个像素值 p ∈ [0, 1] 被视为"每个时间步发放脉冲的概率"。
        在每个时间步 t，生成随机数 r ∈ [0, 1)，
        如果 r < p 则该像素发放脉冲 (spike=1)，否则不发放 (spike=0)。

        经过 T 个时间步，单个像素的总脉冲数 ~ Poisson(p × T)。
        期望脉冲数 = p × T。

        例如：p=0.8, T=50 → 期望 40 个脉冲；p=0.0 → 期望 0 个脉冲。

    【物理类比】
        生物视网膜的神经节细胞：亮像素 → 高发放率，暗像素 → 低发放率。
        这本质上是 rate coding（频率编码）。

    【与硬件电路的对应关系】
        泊松编码可用线性反馈移位寄存器(LFSR)在硬件中高效实现：
        LFSR 产生伪随机数 + 比较器 (r < p?) → 脉冲信号。
        整个编码过程只需 784 个 LFSR + 比较器并行工作，
        无需乘法器，电路开销极小。

    【向量化实现】
        使用 numpy 广播一次性生成 (784, T) 的随机矩阵，
        比逐像素循环快约 100 倍。

    Args:
        image_flat: (784,) 一维向量，每个元素 ∈ [0, 1]
        T:          仿真时间步数
        seed:       随机种子（用于可复现测试，None 时不固定）

    Returns:
        spike_matrix: (784, T) float32 矩阵
                      第 i 行 = 第 i 个像素的 T 步脉冲序列 (0 或 1)
    """
    if seed is not None:
        rng = np.random.RandomState(seed)
    else:
        rng = np.random

    # 向量化实现：一步生成 (784, T) 的随机矩阵并与像素值比较
    # image_flat[:, None] 将 (784,) 广播为 (784, 1)，与 (784, T) 比较
    random_matrix = rng.rand(784, T).astype(np.float32)
    spike_matrix = (random_matrix < image_flat.reshape(-1, 1)).astype(np.float32)

    return spike_matrix


# ============================================================
# 第 5 部分：IF 神经元层
# ============================================================

class IFLayer:
    """单层 Integrate-and-Fire (IF) 脉冲神经元

    【IF 神经元动力学方程】
        V_i[t] = V_i[t-1] + Σ_j (W_ji × S_j[t]) + b_i     (积分/突触整合)
        if V_i[t] >= Vth:
            S_i[t] = 1    (发放脉冲)
            V_i[t] = 0    (膜电位复位 — hard reset)

    【与硬件电路的对应关系】
        MUX 树    ← S_j[t]=1 时选择 +W_ji，S_j[t]=0 时选择 +0
        加法器树  ← 将 MUX 输出累加：I_i = b_i + Σ_j MUX(S_j[t], W_ji, 0)
        寄存器    ← 存储膜电位 V_i (时钟驱动)
        比较器    ← V_i >= Vth ?
        复位逻辑  ← 触发后清零 MUX(Spike, 0, V_i)

    【与 ANN 中 ReLU 的对应关系】
        IF 神经元的脉冲发放率 r ≈ ReLU(W·r_in + b) / Vth
        这是 ANN-to-SNN 转换能工作的数学基础。
        因为 ReLU(x) = max(0, x)，而 IF 神经元的输出频率
        天然 ≥ 0（不可能有"负频率"），且近似与输入成线性关系。

    实现为"一层神经元"（非单个神经元），使用矩阵乘法加速向量化计算。
    """

    def __init__(self, W, b, Vth=1.0, reset_mode="hard"):
        """
        Args:
            W:          权重矩阵，形状 (n_input, n_neurons)
            b:          偏置向量，形状 (n_neurons,)
            Vth:        膜电位触发阈值
            reset_mode: "hard"=触发后清零, "soft"=触发后减去 Vth
        """
        self.W = W.astype(np.float32)
        self.b = b.astype(np.float32)
        self.Vth = float(Vth)
        self.reset_mode = reset_mode
        self.n_neurons = b.shape[0]

        # 膜电位，形状 (n_neurons,)，初始为 0
        self.V = np.zeros(self.n_neurons, dtype=np.float32)

        # 脉冲计数器 —— 记录整张图片推理期间的总脉冲数（用于稀疏性分析）
        self.total_spikes = np.zeros(self.n_neurons, dtype=np.int32)

    def reset(self):
        """重置膜电位和脉冲计数器（每张新图片前必须调用）"""
        self.V.fill(0.0)
        self.total_spikes.fill(0)

    def forward(self, input_spikes):
        """单时间步前向传播

        【步骤详解】
        1. 突触积分：I = input_spikes @ W + b
           由于 input_spikes 只有 0 和 1，矩阵乘法的本质是：
           对每个神经元 j：I_j = b_j + Σ_{i: spike[i]=1} W[i,j]
           这恰好对应硬件中的 MUX + 累加逻辑！

        2. 膜电位更新：V = V + I

        3. 触发判断：output_spike = (V >= Vth)

        4. 膜电位复位：
           - hard: V[spike] = 0       （直接清零，硬件友好）
           - soft: V[spike] -= Vth    （保留余量，更精确但有信息损失）

        Args:
            input_spikes: (n_input,) 当前时间步的输入脉冲向量

        Returns:
            output_spikes: (n_neurons,) 当前时间步的输出脉冲向量
        """
        # 步骤 1 & 2：突触积分 + 膜电位更新
        # np.dot 利用 BLAS 优化，即使向量-矩阵乘法也非常快
        synaptic_input = np.dot(input_spikes, self.W) + self.b
        self.V += synaptic_input

        # 步骤 3：判断哪些神经元膜电位达到或超过阈值
        output_spikes = (self.V >= self.Vth).astype(np.float32)

        # 步骤 4：膜电位复位
        if self.reset_mode == "hard":
            # Hard reset：触发神经元膜电位直接清零
            # 硬件实现：MUX(Spike, 0, V) —— 触发器输出控制 MUX
            self.V[output_spikes > 0] = 0.0
        elif self.reset_mode == "soft":
            # Soft reset：触发神经元减去阈值（保留余量）
            # 优点：不丢失超过 Vth 的那部分膜电位信息
            # 缺点：电路需要减法器而非简单复位，增加硬件开销
            self.V[output_spikes > 0] -= self.Vth

        # 更新脉冲计数统计
        self.total_spikes += output_spikes.astype(np.int32)

        return output_spikes


# ============================================================
# 第 6 部分：两层 SNN 网络
# ============================================================

class SNN:
    """两层全连接脉冲神经网络 (784 → 300 → 10)

    【网络结构】
        输入层 (784)  — 由泊松编码生成的脉冲序列
        隐藏层 (300)  — IF 神经元层，对应 ANN 的 ReLU 隐藏层
        输出层 (10)   — IF 神经元层，脉冲计数取最大 → 分类结果

    【推理流程】
        1. reset() —— 清空所有层的膜电位和脉冲计数
        2. 泊松编码 —— 将 (784,) 图片 → (784, T) 脉冲矩阵
        3. 逐时间步：
           输入脉冲 → Layer1.forward() → 隐藏层脉冲
           隐藏层脉冲 → Layer2.forward() → 输出层脉冲
        4. 统计输出层 T 步的总脉冲数
        5. argmax(输出脉冲计数) → 预测类别

    【为什么输出层不用 Softmax】
        ANN 中 Softmax 的作用是将 logits 归一化为概率分布。
        SNN 的输出是 T 步脉冲计数的累积，本身就是一个"得分"：
        - 正确类别的神经元收到更多兴奋性输入 → 发放更多脉冲
        - 其他类别的神经元收到较少输入 → 发放较少脉冲
        取脉冲计数最大的神经元等价于 ANN 的 argmax，无需 Softmax。
    """

    def __init__(self, W1, b1, W2, b2, Vth=1.0, reset_mode="hard"):
        """
        Args:
            W1, b1: 第 1 层 (784→300) 的权重和偏置（应已归一化）
            W2, b2: 第 2 层 (300→10) 的权重和偏置（应已归一化）
            Vth:    膜电位触发阈值
            reset_mode: 复位模式
        """
        self.layer1 = IFLayer(W1, b1, Vth, reset_mode)
        self.layer2 = IFLayer(W2, b2, Vth, reset_mode)
        self.T = 0  # 记录最近一次推理使用的时间步数

    def reset(self):
        """重置所有层的状态"""
        self.layer1.reset()
        self.layer2.reset()

    def forward(self, image, T, seed=None):
        """完整 SNN 推理（一张图片）

        Args:
            image: (784,) 图片向量，值域 [0, 1]
            T:     仿真时间步数
            seed:  泊松编码的随机种子

        Returns:
            pred:       预测类别 (0-9)
            spike_count: (10,) 输出层 10 个神经元的脉冲总数
        """
        self.T = T
        if T <= 0:
            raise ValueError(f"T 必须为正整数，当前 T={T}")
        self.reset()

        # 步骤 1：泊松编码 —— 图片 → 脉冲序列
        spike_input = poisson_encode(image, T, seed=seed)  # (784, T)

        # 步骤 2 & 3：逐时间步传播
        for t in range(T):
            # 当前时间步输入脉冲 (784,)
            in_spikes = spike_input[:, t]

            # 隐藏层处理：输入脉冲 → 隐藏层脉冲 (300,)
            h_spikes = self.layer1.forward(in_spikes)

            # 输出层处理：隐藏层脉冲 → 输出层脉冲 (10,)
            self.layer2.forward(h_spikes)

        # 步骤 4 & 5：输出层脉冲计数 → 预测
        spike_count = self.layer2.total_spikes.copy()
        if spike_count.sum() == 0:
            # 所有输出神经元均未发放脉冲 → 信息不足，随机预测
            rng = np.random.RandomState(seed)
            pred = rng.randint(0, 10)
        else:
            pred = int(np.argmax(spike_count))

        return pred, spike_count

    def get_spike_stats(self):
        """获取当前推理的脉冲统计信息

        Returns:
            dict: 包含各层的总脉冲数、平均脉冲数、稀疏率
        """
        s1 = self.layer1.total_spikes.sum()
        s2 = self.layer2.total_spikes.sum()

        # 稀疏率 = 1 - (实际发放脉冲数 / 最大可能脉冲数)
        # 最大可能 = 神经元数 × 时间步数（每个时间步都发放）
        max_spikes_l1 = self.layer1.n_neurons * self.T
        max_spikes_l2 = self.layer2.n_neurons * self.T

        return {
            'layer1_total': int(s1),
            'layer2_total': int(s2),
            'layer1_avg_per_neuron': float(s1) / self.layer1.n_neurons,
            'layer2_avg_per_neuron': float(s2) / self.layer2.n_neurons,
            'layer1_sparsity': 1.0 - float(s1) / max(max_spikes_l1, 1),
            'layer2_sparsity': 1.0 - float(s2) / max(max_spikes_l2, 1),
            'overall_sparsity': 1.0 - float(s1 + s2) / max(max_spikes_l1 + max_spikes_l2, 1),
        }


# ============================================================
# 第 7 部分：SNN 测试与评估
# ============================================================

def test_snn(snn, X_test, y_test, T, max_samples=None, verbose=True):
    """在测试集上评估 SNN 的性能

    评估指标：
    - 准确率 (Accuracy)：预测正确的比例
    - 脉冲稀疏率 (Spike Sparsity)：神经元静默的时间比例
      (1 - 实际发放数/最大可能发放数)
      稀疏率越高 → 功耗越低（因为脉冲触发是主要的能耗来源）

    Args:
        snn:         SNN 实例（权重应已归一化）
        X_test:      (n, 784) 测试集图片
        y_test:      (n,) 测试标签
        T:           仿真时间步数
        max_samples: 最多测试张数（None = 全部，用于快速验证）
        verbose:     是否打印进度

    Returns:
        accuracy:      float, 测试准确率
        stats:         dict, 详细的脉冲统计信息
        per_class_acc: dict, 每个数字类别的准确率
    """
    n_total = len(X_test)
    n_test = n_total if max_samples is None else min(max_samples, n_total)

    correct = 0
    total_spikes_l1 = 0
    total_spikes_l2 = 0
    per_class_correct = np.zeros(10, dtype=np.int32)
    per_class_total = np.zeros(10, dtype=np.int32)

    # 设置随机种子以确保泊松编码可复现
    rng = np.random.RandomState(42)

    for i in range(n_test):
        image = X_test[i].astype(np.float32)
        label = y_test[i]

        # SNN 推理
        pred, spike_count = snn.forward(image, T, seed=rng.randint(0, 2**31 - 1))

        if pred == label:
            correct += 1
            per_class_correct[label] += 1
        per_class_total[label] += 1

        # 累加脉冲统计
        stats_i = snn.get_spike_stats()
        total_spikes_l1 += stats_i['layer1_total']
        total_spikes_l2 += stats_i['layer2_total']

        # 打印进度
        if verbose and (i + 1) % 1000 == 0:
            acc_sofar = correct / (i + 1) * 100
            print(f"  进度: {i+1:5d}/{n_test}  |  当前准确率: {acc_sofar:.2f}%")

    accuracy = correct / n_test

    # 汇总脉冲统计
    max_possible_l1 = 300 * T * n_test
    max_possible_l2 = 10 * T * n_test
    max_possible_total = max_possible_l1 + max_possible_l2
    overall_sparsity = 1.0 - (total_spikes_l1 + total_spikes_l2) / max(max_possible_total, 1)

    stats = {
        'n_tested': n_test,
        'T': T,
        'accuracy': accuracy,
        'total_spikes_l1': int(total_spikes_l1),
        'total_spikes_l2': int(total_spikes_l2),
        'avg_spikes_l1_per_image': total_spikes_l1 / n_test,
        'avg_spikes_l2_per_image': total_spikes_l2 / n_test,
        'sparsity_l1': 1.0 - total_spikes_l1 / max(max_possible_l1, 1),
        'sparsity_l2': 1.0 - total_spikes_l2 / max(max_possible_l2, 1),
        'overall_sparsity': overall_sparsity,
    }

    # 各类别准确率
    per_class_acc = {}
    for c in range(10):
        if per_class_total[c] > 0:
            per_class_acc[c] = per_class_correct[c] / per_class_total[c]

    return accuracy, stats, per_class_acc


# ============================================================
# 第 8 部分：结果打印与保存
# ============================================================

def print_results(config, accuracy, stats, per_class_acc):
    """格式化打印 SNN 测试结果"""
    print(f"\n{'='*60}")
    print(f"  SNN 测试结果")
    print(f"{'='*60}")
    print(f"  配置: {config}")
    print(f"  测试样本数: {stats['n_tested']}")
    print(f"{'='*60}")
    print(f"  准确率 (Accuracy):        {accuracy*100:6.2f}%")
    print(f"{'='*60}")
    print(f"  --- 脉冲稀疏性 ---")
    print(f"  第 1 层 (784→300) 平均脉冲数/图片: {stats['avg_spikes_l1_per_image']:8.1f}")
    print(f"  第 1 层 稀疏率:                      {stats['sparsity_l1']*100:6.2f}%")
    print(f"  第 2 层 (300→10)  平均脉冲数/图片:   {stats['avg_spikes_l2_per_image']:8.1f}")
    print(f"  第 2 层 稀疏率:                      {stats['sparsity_l2']*100:6.2f}%")
    print(f"  整体稀疏率:                          {stats['overall_sparsity']*100:6.2f}%")
    print(f"{'='*60}")
    print(f"  --- 各类别准确率 ---")
    for c in range(10):
        marker = " <-- 最低" if per_class_acc.get(c, 0) == min(per_class_acc.values()) else ""
        print(f"  数字 {c}: {per_class_acc.get(c, 0)*100:6.2f}%{marker}")
    print(f"{'='*60}\n")


def save_results(config, accuracy, stats, per_class_acc, output_path):
    """保存 SNN 测试结果到 .npz 文件

    Args:
        config:         SNNConfig 实例
        accuracy:       准确率
        stats:          脉冲统计
        per_class_acc:  各类别准确率
        output_path:    输出文件路径
    """
    # 将配置和结果转为可保存的格式
    save_dict = {
        'T': config.T,
        'Vth': config.Vth,
        'norm_method': config.norm_method,
        'reset_mode': config.reset_mode,
        'accuracy': accuracy,
        'n_tested': stats['n_tested'],
        'overall_sparsity': stats['overall_sparsity'],
        'sparsity_l1': stats['sparsity_l1'],
        'sparsity_l2': stats['sparsity_l2'],
        'total_spikes_l1': stats['total_spikes_l1'],
        'total_spikes_l2': stats['total_spikes_l2'],
    }
    np.savez(output_path, **save_dict)
    print(f"[保存] 测试结果已保存到 {output_path}")


# ============================================================
# 第 9 部分：主函数
# ============================================================

def main():
    """主函数：串联 ANN 权重加载、归一化、SNN 构建、测试全流程"""

    # ---- 路径配置 ----
    base_dir = os.path.dirname(os.path.abspath(__file__))
    weight_path = os.path.join(base_dir, "ann_mnist_weights_relu.npz")
    output_path = os.path.join(base_dir, "snn_results.npz")

    # ---- 命令行参数解析 ----
    # 用法: python snn_conversion.py [max_norm|data_based] [T] [Vth] [max_samples]
    norm_method = sys.argv[1] if len(sys.argv) > 1 else "max_norm"
    T = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    Vth = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
    max_test_samples = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    if max_test_samples == 0:
        max_test_samples = None  # 全部测试

    # ---- 加载 MNIST 数据 ----
    print("=" * 60)
    print("  ANN-to-SNN 转换 & SNN 测试")
    print("=" * 60)
    print("\n[数据加载] 正在加载 MNIST 数据集...")
    mnist = fetch_openml('mnist_784', version=1, as_frame=False, parser='liac-arff')
    X = mnist.data.astype(np.float32) / np.float32(255.0)   # 归一化到 [0, 1]
    y = mnist.target.astype(np.int32)

    train_size = 60000
    X_train, X_test = X[:train_size], X[train_size:]
    y_train, y_test = y[:train_size], y[train_size:]
    print(f"  训练集: {len(X_train)} 张, 测试集: {len(X_test)} 张")

    # ---- 加载 ANN 权重 ----
    print(f"\n[权重加载] 从 {weight_path} 加载...")
    W1, b1, W2, b2 = load_ann_weights(weight_path)

    # ---- 权重归一化 ----
    print(f"\n[权重归一化] 方法: {norm_method}")
    if norm_method == "max_norm":
        (W1_norm, b1_norm), (W2_norm, b2_norm) = max_norm_normalize(W1, b1, W2, b2)
    elif norm_method == "data_based":
        (W1_norm, b1_norm), (W2_norm, b2_norm) = data_based_normalize(
            W1, b1, W2, b2, X_train, Vth=Vth)
    else:
        raise ValueError(f"未知的归一化方法: {norm_method}，请使用 max_norm 或 data_based")

    # ---- 构建 SNN ----
    print(f"\n[SNN 构建] Vth={Vth}, T={T}, reset_mode=hard")
    config = SNNConfig(T=T, Vth=Vth, norm_method=norm_method, reset_mode="hard")
    snn = SNN(W1_norm, b1_norm, W2_norm, b2_norm, Vth=Vth, reset_mode="hard")

    # ---- 测试 SNN ----
    n_test_desc = max_test_samples if max_test_samples else len(X_test)
    print(f"\n[SNN 测试] 在 {n_test_desc} 张测试图片上评估 (T={T})...")
    accuracy, stats, per_class_acc = test_snn(
        snn, X_test, y_test, T, max_samples=max_test_samples, verbose=True)

    # ---- 输出结果 ----
    print_results(config, accuracy, stats, per_class_acc)

    # ---- 保存结果 ----
    save_results(config, accuracy, stats, per_class_acc, output_path)

    # ---- 额外分析：单张图片示例 ----
    print("[示例] 单张图片推理演示 (第一张测试图片):")
    demo_image = X_test[0]
    demo_label = y_test[0]
    snn_demo = SNN(W1_norm, b1_norm, W2_norm, b2_norm, Vth=Vth, reset_mode="hard")
    pred, spike_count = snn_demo.forward(demo_image, T, seed=42)
    demo_stats = snn_demo.get_spike_stats()

    print(f"  真实标签: {demo_label}")
    print(f"  SNN 预测: {pred} {'✓' if pred == demo_label else '✗'}")
    print(f"  输出层脉冲计数: {spike_count}")
    print(f"  第 1 层总脉冲: {demo_stats['layer1_total']}")
    print(f"  第 2 层总脉冲: {demo_stats['layer2_total']}")

    return accuracy, stats


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":
    main()
