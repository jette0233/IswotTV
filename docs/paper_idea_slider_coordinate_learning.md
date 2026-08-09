# 基于深度学习的滑块验证码坐标映射函数学习

## 构思记录

**作者**: Jette  
**日期**: 2026-05-21  
**状态**: 初始构思，待发展

---

## 一、问题背景

### 1.1 滑块验证码的坐标映射难题

学习通（Chaoxing）平台使用滑块验证码（GeeTest风格）作为反爬/反自动化手段。其流程为：

1. 前端通过 `captcha.chaoxing.com` 获取 `conf` → `get/verification/image` → 得到背景图（shadeImage）和滑块图（cutoutImage）
2. 用户拖动滑块将缺口对齐到背景图的指定位置
3. 前端将拖动距离 `x` 通过 `textClickArr=[{"x": x}]` 提交到 `check/verification/result`
4. 验证通过后返回 `validate token`，可用于后续业务请求（签到、登录等）

**核心问题**：`x` 值存在一个**未知的坐标映射函数** $f$，将图像像素坐标系映射到验证码服务端期望的轨道坐标系：

$$x_{\text{submit}} = f(x_{\text{image}}, I_{\text{bg}}, I_{\text{slider}})$$

其中 $x_{\text{image}}$ 是缺口在背景图中的像素位置，但 $f$ 受以下因素影响：
- 滑块轨道的起始偏移量（track offset）
- CSS 缩放比例/Device Pixel Ratio
- 验证码服务端的坐标校验逻辑
- 叠加遮罩对图像特征的影响

### 1.2 传统 CV 方案的失败原因

传统的 OpenCV 模板匹配方案（Canny + TM_CCOEFF_NORMED）在学习通的验证码上持续失败（100% 的 x 值被服务器拒绝），原因推测：

| 因素 | 说明 |
|------|------|
| **遮罩叠加** | 缺口位置的图像被叠加了半透明遮罩（阴影/模糊），改变了纹理特征 |
| **多相似区域** | 背景图中存在与滑块内容相似的多处区域，模板匹配定位到错误位置 |
| **坐标偏移** | 服务端可能不接受图像像素坐标，而是期望经过缩放/偏移后的值 |
| **轨迹验证** | 部分场景下服务端可能验证 `textClickArr` 轨迹的合理性 |

---

## 二、核心思路

### 2.1 核心观测

对于一个给定的验证码实例（背景图 + 滑块图），存在一个**唯一的正确 x 值**，使得 `check/verification/result` 返回 `result: true`。这个 x 值可以通过**暴力验证**获得：在有效时间窗口内，依次尝试不同 x 值，找到第一个返回成功的值。

**关键洞察**：通过大量采样 `(背景图, 滑块图) → 正确 x` 的映射对，可以训练一个深度学习模型来**直接回归 x 值**。

### 2.2 总体框架

```
[数据集构建]           [模型训练]            [部署推理]
                                            
背景图+滑块图           CNN Backbone         新验证码实例
     ↓                     ↓                      ↓
暴力搜索正确x          → 特征提取             → 模型推理
     ↓                     ↓                      ↓
标注数据集             回归头 (x预测)         → 预测 x 值
     ↓                     ↓                      ↓
                        Loss: MSE /           提交验证
                        Huber Loss
```

---

## 三、数据集构建（最关键部分）

### 3.1 自动采样流程

利用 captcha.chaoxing.com API 自动生成训练数据：

```python
for i in range(N_SAMPLES):
    # 1. 获取 conf → image
    service_time = get_conf()
    next_token, shade_url, cutout_url, iv = get_images(cookie, service_time)
    
    # 2. 下载图片
    bg = download(shade_url)
    slider = download(cutout_url)
    
    # 3. 暴力搜索正确 x（0~264，步长1，并行或二分加速）
    correct_x = brute_force_search(next_token, iv, cookie)
    
    # 4. 保存样本
    save(f"sample_{i}_bg.png", bg)
    save(f"sample_{i}_slider.png", slider)
    save(f"sample_{i}_x.txt", correct_x)
    
    # 5. 等待防封
    time.sleep(random.uniform(1, 3))
```

### 3.2 搜索加速策略

暴力搜索 0~264 最多需 265 次请求，可通过以下方式加速：

| 策略 | 复杂度 | 说明 |
|------|--------|------|
| 线性扫描 | O(n) | 从 0 到 264 依次尝试 |
| **二分搜索** | O(log n) | 利用 `[r]`/`[cc]` 错误码判断区间方向（需先确定单调性） |
| 粗搜+精搜 | O(√n) | 先步长10粗搜，再在邻域步长1精搜 |
| OpenCV 初值 | O(1)+O(δ) | 先用 OpenCV 预测初值 $x_0$，只在 $[x_0-δ, x_0+δ]$ 精搜 |

### 3.3 数据集规模估计

| 规模 | 耗时估计 | 预期效果 |
|------|----------|----------|
| 100 样本 | ~30 min | 验证可行性 |
| 1,000 样本 | ~5 hours | 初步可用模型 |
| 10,000 样本 | ~2 days | 高精度模型 |

### 3.4 反爬虫规避

- 请求间隔随机化（1~5s）
- 使用多 Cookie/Session
- 每次获取新 `conf`（避免 token 复用）
- IP 代理轮换（可选）

---

## 四、模型架构方案

### 4.1 方案 A：双流 CNN（推荐）

```
背景图 (320×160) ─→ CNN Backbone ─→ 特征向量 f_bg ─┐
                                                    ├──→ Concat → FC → x
滑块图 (56×160)  ─→ CNN Backbone ─→ 特征向量 f_slider ┘
```

**Backbone 选择**：

| 模型 | 参数量 | 推理速度 | 预期精度 |
|------|--------|----------|----------|
| ResNet-18 | 11M | 快 | ★★★ |
| ResNet-50 | 25M | 中 | ★★★★ |
| MobileNetV3 | 5M | 极快 | ★★★ |
| EfficientNet-B0 | 5M | 快 | ★★★★ |
| ViT-Tiny | 6M | 中 | ★★★★ |

### 4.2 方案 B：单流 Siamese

```
背景图 ──┐
         ├── 共享权重 CNN ──→ 特征提取 ──→ 互相关运算 ──→ x
滑块图 ──┘
```

类似 Siamese Network 结构，通过互相关（cross-correlation）定位滑块在背景图中的位置。

### 4.3 方案 C：端到端坐标回归 Transformer

```
背景图 ──→ Patch Embedding ──┐
                             ├── Transformer Encoder ──→ [CLS] head ──→ x
滑块图 ──→ Patch Embedding ──┘
```

将两张图分别切 patch 后拼接成序列，用 Transformer 建模全局依赖关系。

---

## 五、训练细节

### 5.1 Loss 函数

- **主 Loss**: Huber Loss（对异常值鲁棒）
  $$L_{\delta}(y, \hat{y}) = \begin{cases} \frac{1}{2}(y-\hat{y})^2 & \text{if } |y-\hat{y}| \leq \delta \\ \delta(|y-\hat{y}| - \frac{1}{2}\delta) & \text{otherwise} \end{cases}$$
- **辅助 Loss**: 分类辅助（将 x 离散化为 265 类，用 CrossEntropy Loss）
- **最终 Loss**: $L = L_{\text{huber}} + \alpha \cdot L_{\text{cls}}$

### 5.2 数据增强

| 增强 | 幅度 | 原因 |
|------|------|------|
| 随机亮度 | ±10% | 模拟不同光照条件 |
| 随机对比度 | ±10% | 同上 |
| 高斯噪声 | σ≤2 | 模拟压缩伪影 |
| 随机裁剪（边缘） | ≤5px | 提高边缘鲁棒性 |

### 5.3 评估指标

| 指标 | 说明 | 目标值 |
|------|------|--------|
| MAE | 平均绝对误差 (px) | < 3px |
| RMSE | 均方根误差 (px) | < 5px |
| Acc@3 | 预测值与真实值误差 ≤3px 的比例 | > 95% |
| Pass Rate | 验证码通过率（实际业务验证） | > 90% |

---

## 六、与传统 OpenCV 方案的对比实验

| 维度 | OpenCV (Canny+TM_CCOEFF) | 深度学习 (本方案) |
|------|--------------------------|-------------------|
| 精度 | 0%（持续 verification error） | 预期 >90% |
| 推理速度 | ~50ms | ~10-50ms (GPU) / ~100ms (CPU) |
| 训练成本 | 无 | 需 1,000+ 标注样本 |
| 鲁棒性 | 对遮罩/相似区域敏感 | 可通过学习忽略噪声 |
| 可扩展性 | 每个新验证码类型需调参 | 同架构可迁移 |
| 依赖 | OpenCV + numpy | PyTorch/TensorFlow |

---

## 七、潜在扩展

### 7.1 多任务学习

同时学习多个输出：
- x 坐标（回归）
- 滑块类型分类（slide / rotate / text_click / icon_click）
- 验证码难度估计

### 7.2 域适应（Domain Adaptation）

当验证码样式更新时，用少量新样本（~50）微调即可适配，无需重新采样。

### 7.3 验证码安全评估

反过来分析坐标映射函数 $f$ 的性质，评估验证码系统的安全性：
- 映射是否线性？是否存在可被利用的漏洞？
- 是否可通过对 $f$ 的分析绕过验证？

---

## 八、可投稿的会议/期刊

### 8.1 计算机视觉与安全交叉

| 会议/期刊 | 等级 | 匹配度 | 说明 |
|-----------|------|--------|------|
| **CCS** (ACM Conf. on Computer and Communications Security) | CCF-A | ★★★ | 安全顶会，验证码攻防方向 |
| **NDSS** (Network and Distributed System Security) | CCF-A | ★★★ | 网络安全顶会 |
| **USENIX Security** | CCF-A | ★★★ | 安全顶会 |
| **S&P** (IEEE Symposium on Security and Privacy) | CCF-A | ★★★ | 安全顶会 |
| **EuroS&P** | CCF-B | ★★★ | 欧洲安全会议 |
| **Computers & Security** (Elsevier) | CCF-B / SCI | ★★★ | 安全期刊 |

### 8.2 计算机视觉方向

| 会议/期刊 | 等级 | 匹配度 | 说明 |
|-----------|------|--------|------|
| **CVPR** (IEEE/CVF Conf. on Computer Vision and Pattern Recognition) | CCF-A | ★★ | 视觉顶会，需更强的通用性 |
| **ICCV** (International Conf. on Computer Vision) | CCF-A | ★★ | 同上 |
| **ECCV** (European Conf. on Computer Vision) | CCF-B | ★★ | 同上 |
| **Pattern Recognition** (Elsevier) | CCF-B / SCI | ★★★ | 模式识别期刊，适合方法论 |

### 8.3 人工智能应用方向

| 会议/期刊 | 等级 | 匹配度 | 说明 |
|-----------|------|--------|------|
| **AAAI** (AAAI Conf. on Artificial Intelligence) | CCF-A | ★★ | AI 顶会，需方法创新 |
| **IJCAI** (International Joint Conf. on AI) | CCF-A | ★★ | 同上 |
| **NeurIPS** (Neural Information Processing Systems) | CCF-A | ★★ | 同上 |
| **Engineering Applications of AI** (Elsevier) | CCF-C / SCI | ★★★ | 工程应用期刊 |
| **Expert Systems with Applications** (Elsevier) | CCF-C / SCI | ★★★ | 应用型期刊，易中 |

### 8.4 推荐投稿路径

**最务实路径**（本科生可触及）：

```
1. IEEE Access (SCI, 开源期刊) — 门槛最低，版面费 $1,950
2. Engineering Applications of AI (CCF-C/SCI) — 需要一定创新
3. Expert Systems with Applications (CCF-C/SCI) — 实用性导向
4. Computers & Security (CCF-B/SCI) — 安全方向
```

**冲刺目标**：

```
EuroS&P (CCF-B) 或 AAAI (CCF-A) 的 Workshop Track
```

---

## 九、可行性评估

| 维度 | 评估 |
|------|------|
| **技术可行性** | ✅ 高 — 核心难点在数据采集，建模部分有成熟方案 |
| **数据获取** | ⚠️ 中 — 需自动化暴力搜索，注意反爬策略 |
| **创新性** | ⚠️ 中 — 验证码破解非新方向，但"坐标映射函数学习"的角度有独特价值 |
| **实验工作量** | ⚠️ 中 — 需 1-2 周数据采集 + 1 周模型训练调优 |
| **论文写作** | ✅ 高 — 有清晰的 baseline 对比和 ablation study 空间 |
| **发表难度** | ⚠️ 中 — CCF-C 以上需要充分的实验对比和 ablation |

---

## 十、后续行动计划

- [ ] Phase 1: 自动化数据采集脚本（暴力搜索正确 x）
- [ ] Phase 2: 收集 100 样本，验证深度学习可行性
- [ ] Phase 3: 收集团队千级别数据集，训练基线模型
- [ ] Phase 4: 与 OpenCV baseline 对比，撰写论文
- [ ] Phase 5: 投稿

---

## 附录：2026-05-22 逆向最终结论

### 验证码系统安全架构

```
v8.chaoxing.com (登录页)                captcha.chaoxing.com (验证码服务)
       │                                        │
       │── get/conf (JSONP) ──────────────────→ ✅
       │── get/verification/image (JSONP) ────→ ✅
       │                                        │
       │   check/verification/result ─────────→ ❌ (同源保护)
       │   (CORS: v8.chaoxing.com 不可访问)      │
       │                                        │
  captcha.chaoxing.com/load.min.js
  （← 作为 script 标签加载）
       │
       │── check/verification/result ─────────→ ✅
       │   (captcha.chaoxing.com 同源调用)
```

### 关键发现
1. `check/verification/result` 端点有严格 CORS 保护，仅允许 `captcha.chaoxing.com` 同源调用
2. `get/conf` 和 `get/verification/image` 通过 JSONP 支持跨域（设计上必须）
3. `load.min.js` 作为 script 标签从 `v8.chaoxing.com` 加载，但其内部 AJAX 请求受 CORS 限制
4. captcha 的真实验证逻辑运行在 `captcha.chaoxing.com/load.min.js` 中，通过 postMessage 或其他方式与主页面通信

### 对数据采样的影响
- **check 端点不可跨域调用** → 无法通过 Python/浏览器 fetch 进行自动化的 x 值暴力搜索
- **解决方案**：通过`get/conf` → `get/verification/image` 获取图片后，以截图 diff（JPG vs 渲染截图）方式找到缺口位置 x，再通过 `load.min.js` 的后续回调获取 validate token
- 或：在真实登录流程中手动完成验证码，捕获正确的 (图片, x) 训练对

---

*本文档由 Jette 构思，Buddy 辅助整理，2026-05-21，更新于 2026-05-22*
