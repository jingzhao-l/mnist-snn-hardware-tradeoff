import numpy as np
import matplotlib.pyplot as plt
from sklearn.datasets import fetch_openml

# ============================================================
# 超参数设置
# ============================================================
num_epochs = 30         # 训练轮数
batch_size = 64         # 每批样本数
learning_rate = 0.01    # 学习率

# ============================================================
# 加载 MNIST 数据
# ============================================================
print("正在加载 MNIST 数据...")
mnist = fetch_openml('mnist_784', version=1, as_frame=False)
X = mnist.data.astype(np.float32) / np.float32(255.0)   # 归一化到 [0,1]
y = mnist.target.astype(np.int32)

train_size = 60000
X_train, X_test = X[:train_size], X[train_size:]
y_train, y_test = y[:train_size], y[train_size:]

n_train = X_train.shape[0]
n_test  = X_test.shape[0]
print(f"训练集: {n_train} 张, 测试集: {n_test} 张")


# ============================================================
# 网络结构: 784 → 300 → 10  (ReLU 激活 + Softmax 输出)
# ============================================================
class MLP:
    def __init__(self):
        # Kaiming / He 初始化: W ~ N(0, sqrt(2/fan_in))
        # 防止 ReLU 神经元在训练初期大量"死亡"（输出恒为 0）
        self.W1 = (np.random.randn(784, 300) * np.sqrt(2.0 / 784)).astype(np.float32)
        self.b1 = np.zeros(300, dtype=np.float32)
        self.W2 = (np.random.randn(300, 10)  * np.sqrt(2.0 / 300)).astype(np.float32)
        self.b2 = np.zeros(10, dtype=np.float32)

    # ----------------------------------------------------------
    # ReLU 激活函数及其导数
    # ----------------------------------------------------------
    @staticmethod
    def relu(z):
        """ReLU: f(z) = max(0, z)"""
        return np.maximum(0, z)

    @staticmethod
    def relu_derivative(z):
        """ReLU 导数: f'(z) = 1 (z>0), 0 (z<=0)"""
        return (z > 0).astype(np.float32)

    # ----------------------------------------------------------
    # Softmax 函数 (数值稳定版)
    # ----------------------------------------------------------
    @staticmethod
    def softmax(z):
        """Softmax: p_i = exp(z_i) / sum_j exp(z_j)"""
        z_stable = z - np.max(z, axis=1, keepdims=True)  # 防溢出
        exp_z = np.exp(z_stable)
        return exp_z / np.sum(exp_z, axis=1, keepdims=True)

    # ----------------------------------------------------------
    # 前向传播
    # ----------------------------------------------------------
    def forward(self, x):
        """
        前向传播:
          z1 = x·W1 + b1     (784→300)
          a1 = ReLU(z1)       (隐藏层激活)
          z2 = a1·W2 + b2    (300→10)
          p  = Softmax(z2)   (输出概率)
        """
        self.z1 = np.dot(x, self.W1) + self.b1       # (N, 300)
        self.a1 = self.relu(self.z1)                  # (N, 300)
        self.z2 = np.dot(self.a1, self.W2) + self.b2  # (N, 10)
        self.probs = self.softmax(self.z2)             # (N, 10)
        return self.probs

    # ----------------------------------------------------------
    # 交叉熵损失
    # ----------------------------------------------------------
    def compute_loss(self, probs, labels):
        """
        Cross-Entropy Loss:
          L = -1/N * sum_i log(p_i[y_i])
        """
        N = probs.shape[0]
        # 取正确标签对应的概率, 加 epsilon 防 log(0)
        correct_probs = probs[np.arange(N), labels]
        # 用 float32 epsilon 的合理倍数防 log(0)
        loss = -np.mean(np.log(correct_probs + 1e-8))
        return loss

    # ----------------------------------------------------------
    # 反向传播 (全部手写推导)
    # ----------------------------------------------------------
    def backward(self, x, labels):
        """
        链式法则逐层求梯度:

        (1) 输出层 — Softmax + CrossEntropy 联合梯度:
            ∂L/∂z2 = softmax(z2) - y_onehot
            (这是经典简化结果, 推导见文档 1.8 节)

        (2) 隐藏层 — ReLU 反向:
            ∂L/∂z1 = (∂L/∂a1) · ReLU'(z1)
            其中 ∂L/∂a1 = ∂L/∂z2 · W2^T
        """
        N = x.shape[0]

        # 构造 one-hot 标签
        y_onehot = np.zeros((N, 10))
        y_onehot[np.arange(N), labels] = 1

        # ---- 输出层梯度 ----
        # dL/dz2 = softmax(z2) - y  (联合梯度简化)
        dz2 = self.probs - y_onehot                            # (N, 10)

        dW2 = np.dot(self.a1.T, dz2) / N                      # (300, 10)
        db2 = np.sum(dz2, axis=0) / N                          # (10,)

        # ---- 隐藏层梯度 ----
        # dL/da1 = dz2 · W2^T
        da1 = np.dot(dz2, self.W2.T)                           # (N, 300)
        # dL/dz1 = dL/da1 ⊙ ReLU'(z1)
        dz1 = da1 * self.relu_derivative(self.z1)              # (N, 300)

        dW1 = np.dot(x.T, dz1) / N                             # (784, 300)
        db1 = np.sum(dz1, axis=0) / N                          # (300,)

        return dW1, db1, dW2, db2

    # ----------------------------------------------------------
    # 参数更新
    # ----------------------------------------------------------
    def update(self, dW1, db1, dW2, db2, lr):
        self.W1 -= lr * dW1
        self.b1 -= lr * db1
        self.W2 -= lr * dW2
        self.b2 -= lr * db2


# ============================================================
# 训练循环
# ============================================================
mlp = MLP()
loss_history = []
acc_history = []

print(f"\n开始训练 (ReLU + Softmax + CrossEntropy, numpy 手写)")
print(f"网络结构: 784 → 300 → 10  |  参数: {784*300+300 + 300*10+10:,} 个")
print(f"epochs={num_epochs}, batch={batch_size}, lr={learning_rate}\n")

for epoch in range(num_epochs):
    # 每个 epoch 打乱训练数据
    perm = np.random.permutation(n_train)
    X_shuffled = X_train[perm]
    y_shuffled = y_train[perm]

    epoch_loss = 0
    n_batches = 0

    for i in range(0, n_train, batch_size):
        X_batch = X_shuffled[i:i+batch_size]
        y_batch = y_shuffled[i:i+batch_size]

        # 前向传播
        probs = mlp.forward(X_batch)
        loss = mlp.compute_loss(probs, y_batch)

        # 反向传播
        dW1, db1, dW2, db2 = mlp.backward(X_batch, y_batch)

        # 参数更新
        mlp.update(dW1, db1, dW2, db2, learning_rate)

        epoch_loss += loss
        n_batches += 1

    avg_loss = epoch_loss / n_batches
    loss_history.append(avg_loss)

    # 每个 epoch 评估测试准确率
    test_probs = mlp.forward(X_test)
    test_pred = np.argmax(test_probs, axis=1)
    test_acc = np.mean(test_pred == y_test)
    acc_history.append(test_acc)

    print(f"Epoch {epoch+1:3d}/{num_epochs}  |  Loss: {avg_loss:.4f}  |  Test Acc: {test_acc*100:.2f}%")


# ============================================================
# 最终评估
# ============================================================
test_probs = mlp.forward(X_test)
test_pred = np.argmax(test_probs, axis=1)
final_acc = np.mean(test_pred == y_test)

print(f"\n{'='*60}")
print(f"最终测试准确率: {final_acc*100:.2f}%")
print(f"{'='*60}")

# 保存权重 (供 ANN-to-SNN 转换使用)
np.savez('ann_mnist_weights_relu.npz',
         W1=mlp.W1, b1=mlp.b1,
         W2=mlp.W2, b2=mlp.b2)
print("权重已保存到 ann_mnist_weights_relu.npz")


# ============================================================
# 绘制训练曲线
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

axes[0].plot(loss_history, 'b-', label='Training Loss')
axes[0].set_xlabel('Epoch')
axes[0].set_ylabel('Cross-Entropy Loss')
axes[0].set_title('Training Loss (ReLU + Softmax + CrossEntropy)')
axes[0].legend()
axes[0].grid(True)

axes[1].plot(range(1, num_epochs+1), [a*100 for a in acc_history], 'g-o', label='Test Accuracy')
axes[1].axhline(y=95, color='r', linestyle='--', label='95% 目标线')
axes[1].set_xlabel('Epoch')
axes[1].set_ylabel('Accuracy (%)')
axes[1].set_title('Test Accuracy per Epoch')
axes[1].legend()
axes[1].grid(True)

plt.tight_layout()
plt.savefig('training_loss_relu.png', dpi=150)
print("训练曲线图已保存到 training_loss_relu.png")
plt.show()
