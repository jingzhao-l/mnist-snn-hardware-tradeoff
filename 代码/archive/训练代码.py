import numpy as np
import matplotlib.pyplot as plt
from sklearn.datasets import fetch_openml

# 设置超参数
num_epochs = 50  # 训练的周期
batch_size = 100  # 批训练的数量
learning_rate = 0.1  # 学习率

# 导入训练数据
mnist = fetch_openml('mnist_784', version=1)
X = mnist.data / 255.0  # 数据标准化
y = mnist.target.astype(int)

# 划分训练集和测试集
train_size = 60000
X_train, X_test = X[:train_size], X[train_size:]
y_train, y_test = y[:train_size], y[train_size:]

# 定义一个简单的神经网络模型结构
class MLP:
    def __init__(self):
        self.layer1_weights = np.random.randn(784, 300) * 0.01
        self.layer1_bias = np.zeros(300)
        self.layer2_weights = np.random.randn(300, 10) * 0.01
        self.layer2_bias = np.zeros(10)

    def sigmoid(self, x):
        return 1 / (1 + np.exp(-x))

    def forward(self, x):
        self.layer1_output = self.sigmoid(np.dot(x, self.layer1_weights) + self.layer1_bias)
        self.output = self.sigmoid(np.dot(self.layer1_output, self.layer2_weights) + self.layer2_bias)
        return self.output

    def compute_loss(self, predictions, labels):
        num_examples = predictions.shape[0]
        labels_one_hot = np.zeros_like(predictions)
        labels_one_hot[np.arange(num_examples), labels] = 1
        loss = np.mean((predictions - labels_one_hot) ** 2)
        return loss

    def compute_accuracy(self, predictions, labels):
        return np.mean(np.argmax(predictions, axis=1) == labels)

# 实例化模型
mlp = MLP()

# 记录损失值
loss_values = []

# 训练循环
for epoch in range(num_epochs):
    for i in range(0, len(X_train), batch_size):
        # 获取一个批次的数据
        X_batch = X_train[i:i + batch_size]
        y_batch = y_train[i:i + batch_size]

        # 前向传播
        outputs = mlp.forward(X_batch)

        # 计算损失
        loss = mlp.compute_loss(outputs, y_batch)

        # 反向传播
        # 计算输出层梯度
        num_examples = X_batch.shape[0]
        labels_one_hot = np.zeros_like(outputs)
        labels_one_hot[np.arange(num_examples), y_batch] = 1
        doutputs = 2 * (outputs - labels_one_hot) / num_examples

        # 计算输出层参数的梯度
        dlayer2_weights = np.dot(mlp.layer1_output.T, doutputs * outputs * (1 - outputs))
        dlayer2_bias = np.sum(doutputs * outputs * (1 - outputs), axis=0)

        # 计算隐藏层梯度
        dlayer1_output = np.dot(doutputs * outputs * (1 - outputs), mlp.layer2_weights.T)
        dlayer1_output *= mlp.layer1_output * (1 - mlp.layer1_output)

        # 计算隐藏层参数的梯度
        dlayer1_weights = np.dot(X_batch.T, dlayer1_output)
        dlayer1_bias = np.sum(dlayer1_output, axis=0)

        # 参数更新
        mlp.layer1_weights -= learning_rate * dlayer1_weights
        mlp.layer1_bias -= learning_rate * dlayer1_bias
        mlp.layer2_weights -= learning_rate * dlayer2_weights
        mlp.layer2_bias -= learning_rate * dlayer2_bias

        loss_values.append(loss)

        if (i // batch_size + 1) % 100 == 0:
            print('Epoch [{}/{}], Step [{}/{}], Loss: {:.4f}'.format(epoch + 1, num_epochs, i // batch_size + 1,
                                                                     len(X_train) // batch_size, loss))

# 绘制损失图
plt.figure(figsize=(10, 5))
plt.plot(loss_values, label='Training Loss')
plt.xlabel('Iteration')
plt.ylabel('Loss')
plt.title('Training Loss over Time')
plt.legend()
plt.grid(True)
plt.show()

# 测试模型
def predict(model, X):
    return np.argmax(model.forward(X), axis=1)

y_pred = predict(mlp, X_test)
accuracy = np.mean(y_pred == y_test)
print('测试准确率: {:.4f} %'.format(accuracy * 100))
