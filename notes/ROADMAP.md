# RepoRepair-Lab 技术路线与面试叙事

> 面向面试准备：先讲清楚「做了什么、为什么这么做」，再讲「下一步怎么走」。
> 所有数字都来自本仓库的真实运行记录，可直接引用。

---

## 1. 一句话介绍

**RepoRepair-Lab**：一个基于可验证反馈的 Coding Agent 后训练系统。
用 SWE-bench 真实仓库任务做数据，自研 Harness 采集轨迹，QLoRA 做 SFT，用官方测试作为 reward 做强化学习，最后统一评测 Base / SFT / RL。

核心主张：**Agent 的能力不靠人工标注，靠可执行测试给出的二值反馈**。

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│ 任务层                                                       │
│  SWE-bench Lite 300 条 → 过滤/去重/仓库级切分                 │
│  训练集 52 条（8 仓库）   评测集 20 条（2 仓库，零重叠）        │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│ 采集层（本地 Docker）                                        │
│  Agent 容器：原始镜像，无任务目录挂载（防泄漏）                 │
│  验证容器：全新容器，agent patch + 官方 test patch             │
│  判决：pytest returncode == 0                                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│ 训练层（服务器 A10 24GB）                                     │
│  QLoRA：4-bit NF4 + LoRA r=16 + gradient checkpointing        │
│  只监督 assistant token（user/tool 全部 mask）                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│ 评测层                                                       │
│  同一套 Agent 配置，Base / SFT / RL 对比通过率、步数、成本      │
└─────────────────────────────────────────────────────────────┘
```

**为什么本地采集、服务器训练**：
本地能拉 Docker 镜像（服务器 DNS 被污染），服务器有 GPU（本地只有 4GB 显卡）。两边用 rsync 同步数据和代码。

---

## 3. 数据采集：每一步为什么这么做

### 3.1 任务集构建

```
SWE-bench Lite 300 条
  ├─ 剔除测试 ID 不可选中的（换行/括号截断）  → 去掉 25 条
  ├─ 去重
  └─ 仓库级切分（repo-level split）
       训练仓库 8 个：astropy / matplotlib / seaborn / flask
                    requests / xarray / pylint / sphinx
       评测仓库 2 个：scikit-learn / pytest
```

**为什么按仓库切分而不是随机切分**：
同一仓库的 issue 和修复模式高度相似。随机切分会让模型在训练集里见过评测仓库的代码风格，评测结果虚高。仓库级切分是 SWE-bench 的标准做法。

### 3.2 每条任务的「体检」

采集前，每个任务必须通过：

```
① 应用官方 test.patch
② 跑官方测试        → 必须失败（baseline 不能本来就过）
③ 应用 gold.patch
④ 再跑官方测试      → 必须通过
```

**为什么**：
- baseline 本来就过 → 测试没覆盖 bug，任务无意义
- gold 都过不了 → 镜像或测试 ID 有问题，采出来的数据不可信

这一轮 52 条训练任务最终 45 条可用，7 条被拒（httpbin 行为漂移、epub 依赖等）。

### 3.3 双容器采集

```
Agent 容器（--rm，无挂载）
  ├─ 镜像：swebench/sweb.eval.x86_64.<instance_id>
  ├─ 工作目录：/testbed（base commit）
  ├─ 看不到 gold.patch / test.patch
  └─ DeepSeek 生成 bash 命令 → docker exec → 输出回填

验证容器（--rm，挂载 /rrl:ro）
  ├─ 应用 agent patch
  ├─ 应用官方 test.patch
  ├─ pytest 跑 FAIL_TO_PASS + PASS_TO_PASS 的精确 ID
  └─ returncode == 0 → passed
```

**为什么必须两个容器**：
任务目录里有标答和测试补丁。Agent 容器一旦挂载，模型一条 `cat /rrl/gold.patch` 就作弊了。验证必须在全新容器里做，Agent 无法污染。

**工程细节**：
- 补丁用 base64 传入容器（避免引号/换行被 shell 破坏）
- 测试 ID 用 base64 编码的 JSON 传（参数化测试 ID 含引号/括号）
- 判决只看 returncode，不解析 "X passed"（嵌套 pytest 会污染摘要）

### 3.4 资源管理

```
按仓库分组：拉镜像 → 验证 → rollout → 删除镜像
任何时刻磁盘上只有一个仓库的镜像
每条 rollout 立即追加 manifest.jsonl（中断不丢数据）
磁盘低于 50GiB 自动中止
```

**为什么按仓库而不是按任务**：同仓库镜像共享大部分层（conda 环境、系统库），一次拉全仓库可以复用。

### 3.5 真实结果

| 指标 | 数值 |
|---|---|
| 完整任务 | 45 / 52 |
| rollout 总数 | 135（45 × 3） |
| 通过 | 48（36%） |
| 总成本 | $1.12 |
| 单条平均成本 | $0.008 |

---

## 4. 清洗与 SFT

### 4.1 清洗流程

```
135 条 traj.json
  ├─ ① 过滤：final.passed == True        → 保留 48，丢弃 87
  ├─ ② 去重：命令序列 SHA1，保留最便宜的
  ├─ ③ 转换：harness 轨迹 → OpenAI chat 格式
  │     删除 extra 内部字段
  │     删除 role=exit 的结束消息（harness 脚手架）
  │     保留 tool_calls 和 tool_call_id
  └─ ④ 导出 data/clean/sft.jsonl（48 条，4.2MB）
```

**为什么只留成功轨迹**：SFT 是行为克隆，失败轨迹里的动作是错的。失败轨迹留给 RL/DPO。

**为什么删 exit 消息**：`COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` 是 harness 协议，不是模型该学的东西。

**为什么保留 tool_call_id**：模型用原生 function calling，tool 回复必须和 assistant 调用配对，否则训练框架直接报错。

### 4.2 QLoRA 训练

| 参数 | 值 | 理由 |
|---|---|---|
| 量化 | 4-bit NF4 + double quant | 7B fp16 要 15GB，24GB 卡放不下训练状态 |
| LoRA | r=16, alpha=32, 全线性层 | 小数据，rank 太高易过拟合 |
| max_seq_len | 5888 | A10 实测上限（8192 OOM） |
| batch | 1 × grad_accum 4 | 显存约束 |
| lr | 2e-4, cosine, warmup 3% | LoRA 常用 |
| Loss | 只在 assistant token | 否则模型会学着「生成观测」 |

**关键实现**：
- **增量渲染 chat template**：逐条消息渲染并取 token 增量，精确知道哪些 token 属于 assistant（包括 tool_calls）
- **分块交叉熵（chunk=512）+ 梯度检查点**：标准 CE 要把 15 万词表整体上采样到 fp32，一次 5GB，直接 OOM
- **超长轨迹保留头尾**：保留 system+user 和最近的成功步骤，按消息边界裁剪，避免切断 tool_call 配对

**训练结果**：37 train / 9 val，30 步，14.3 分钟，eval_loss 0.514 → 0.418 → 0.407。

---

## 5. 评测（Phase 6）

### 5.1 架构

```
本地 Agent（Docker）── SSH 隧道 ──▶ 服务器 vLLM（A10）
                                      ├─ base
                                      └─ sft (LoRA adapter)
```

**为什么不在服务器上跑 Agent**：服务器拉不了 Docker 镜像。模型必须在 GPU 上，Agent 必须在有镜像的机器上。

### 5.2 首轮结果

| | base | sft |
|---|---|---|
| 通过 | 0/20 | 0/20 |
| 平均步数 | 0.9 | 24.1 |
| 空补丁 | 16/20 | 20/20 |
| 退出状态 | Submitted 14 / FormatError 6 | MaxSteps 8 / FormatError 6 / Error 6 |

**怎么解读**（面试重点）：
- base 几乎不工作：直接提交空补丁或格式错误
- SFT 学会了 Agent 协议（会连续调用工具），但没学会修复技能：诊断显示它重复执行相同的 `grep`/`sed`，从不编辑文件
- 原因：37 条样本 × 30 个优化步，只够学格式，不够学能力

**诚实的结论**：这一轮验证的是链路，不是能力。数据体检显示训练数据本身健康（48 条全部含编辑命令，平均编辑占比 22%），问题在训练量。

---

## 6. 如果 SFT 效果好，下一步怎么走

> 面试时被问「然后呢」，按这个顺序讲。

### 6.1 先定义「效果好」

不能只说通过率涨了，要能区分：

| 维度 | 指标 |
|---|---|
| 主指标 | held-out 通过率（仓库级切分） |
| 行为指标 | 平均步数、空补丁率、格式错误率、重复命令率 |
| 成本指标 | 每任务 token / 耗时 / 单条成本 |
| 统计性 | 20 条太少，至少 50–100 条看置信区间 |

关键话术：**「要能区分是学会了修复，还是只学会了格式」**——我们的 0% 就是反面教材。

### 6.2 Phase 5：可验证奖励 + RL

**为什么 SFT 之后还要 RL**：
- SFT 只能学成功轨迹，失败轨迹全浪费
- 模型学的是「平均行为」，不区分好坏
- RL 能用真实测试做 reward，让模型自己探索

**GRPO 怎么跑**：
```
每个任务采样 K 条 rollout
  → 每条跑官方测试，reward ∈ {0,1}（或部分分）
  → 组内归一化：advantage = (r - mean) / std
  → 用 advantage 加权更新，加 KL 惩罚
```

**为什么 GRPO 不用 PPO**：PPO 要单独的 value network，24GB 显存不够；GRPO 用组内均值当 baseline，省掉 critic。

**工程难点**：
| 问题 | 解法 |
|---|---|
| 奖励稀疏（全 0） | 先保证策略有非零成功率；加部分分 |
| 采样成本 | K 倍成本，用 vLLM 批量采样摊薄 |
| Reward hacking | 独立验证容器 + 只读测试补丁 |
| 训练不稳定 | 小 KL、小 lr、先小规模验证 |
| 显存 | 采样用 vLLM，训练用 transformers，分开跑 |

**实现路线：先 RFT，再 GRPO**
1. **RFT / STaR**：用当前策略采样 N 次 → 保留成功 → 加入 SFT 数据 → 重训
   - 工程简单，本质是自我蒸馏
2. **GRPO**：RFT 收益饱和后再上，用 TRL `GRPOTrainer`

### 6.3 Phase 6：三方统一评测

```
通过率
  │        ╭── RL
  │    ╭───╯
  │ ╭──╯ SFT
  │─╯ Base
  └────────────── 训练数据量
```

固定协议：同一套 Agent 配置、同一批 held-out 任务、同一套评分、记录 token/耗时/成本。

**话术**：「评测看准确率 / 成本 / 步数的三角，生产环境里 agent 的 token 成本很关键。」

### 6.4 数据飞轮

```
采集 → 清洗 → SFT → 评测
  ↑                    ↓
  └── RL 采样 ←── 失败案例分析
```

- 失败轨迹做错误分类（格式错 / 没编辑 / 改错文件 / 测试没跑对）
- 针对每类补数据或改 prompt
- RL 采样的成功轨迹反哺 SFT

**话术**：「模型训练是数据工程，不是调参。」

### 6.5 工程化（如果面试偏 infra）

- 推理：vLLM + LoRA 热加载，多 adapter 共享底座
- 训练：QLoRA + gradient checkpointing + 分块 CE
- 评测：容器隔离、镜像分批拉删、磁盘守卫、断点续跑
- 可观测性：每条 rollout 的 reward / 步数 / 成本 / 失败原因落盘

---

## 7. 真实踩过的坑（面试深挖点）

| # | 坑 | 现象 | 解法 |
|---|---|---|---|
| 1 | 测试泄漏 | Agent 能看到标答 | Agent 容器不挂载任务目录 |
| 2 | FAIL_TO_PASS 是 JSON 字符串 | 88 个 ID 被拆成字符 | `as_list()` |
| 3 | 测试 ID 含换行/截断 | pytest not found | `has_unselectable_ids()`，剔除 25 条 |
| 4 | 嵌套 pytest 污染计数 | gold 全过却判失败 | 判决只看 returncode |
| 5 | pytest 彩色输出 | `\x1b[1m10 passed` 中 `m` 和 `1` 之间无词边界 | 解析前 `strip_ansi()` |
| 6 | certifi 过旧 | HTTPS 测试 `CERTIFICATE_VERIFY_FAILED` | 注入 `REQUESTS_CA_BUNDLE` 指向系统 CA |
| 7 | Docker vhdx 只增不减 | 镜像删了 C 盘不回升 | 停 Docker + diskpart compact（需 UAC） |
| 8 | transformers 5.x 在 Python 3.10 崩溃 | `NameError: nn` | 固定 `transformers<5` |
| 9 | torch CUDA 13 与驱动不兼容 | 驱动 550 只支持 CUDA 12.4 | 固定 `torch==2.5.1` |
| 10 | `prepare_model_for_kbit_training` 转 fp32 | 多占 4.4GB，logits fp32 | 之后手动转回 bf16 |
| 11 | 标准交叉熵 OOM | 15 万词表上采样到 fp32 | 分块 CE + 梯度检查点 |
| 12 | vLLM 0.7.3 没有 Qwen 工具解析器 | base 输出 `<function .../>` 不被识别 | 自写解析插件，兼容 6 种格式 |
| 13 | base 模型写 markdown 不调工具 | 解析器拿不到 action | 解析 ```bash 代码块兜底 |
| 14 | 模型跑完整测试套件 | 单条命令卡 15 分钟 | 评测单命令超时降到 300s |
| 15 | Docker 频繁启停导致 cwd 失效 | `FileNotFoundError` | `os.chdir("/")` + 绝对路径 |

---

## 8. 面试问答速查

**Q：为什么用两个容器？**
Agent 容器如果挂载任务目录，模型能直接读 gold.patch。验证容器必须全新，Agent 无法污染。

**Q：为什么判决只看 returncode？**
嵌套 pytest（pytest 自己的测试套件）会把子进程的摘要混进输出，解析文本会误判。returncode 是唯一可靠的信号。

**Q：为什么 36% 通过率是合理的？**
DeepSeek 在 SWE-bench Lite 公开水平约 40%，我们给 40 步、temperature=0，36% 在合理范围。这个数字本身就是 baseline。

**Q：为什么 SFT 只导出成功轨迹？**
SFT 是行为克隆，失败轨迹的动作是错的。失败轨迹用于 DPO/拒绝采样，不属于 SFT。

**Q：为什么 GRPO 不用 PPO？**
PPO 需要 value network，7B 模型在 24GB 卡上放不下；GRPO 用组内均值当 baseline。

**Q：SFT 评测 0% 是不是系统有问题？**
不是。链路全通（模型会连续调用工具、验证器正常打分），是训练量不足（37 条 × 30 步）。数据体检显示训练数据健康。

**Q：怎么防止 reward hacking？**
独立验证容器、测试补丁只读、Agent 不挂载任务目录、只跑官方测试 ID。

**Q：数据量这么少为什么还做？**
这是链路验证，不是刷榜。先用最小闭环把采集→清洗→训练→评测跑通，再扩数据。工程上每一步都有可复用的产出。

---

## 9. 三分钟自我介绍模板

> 「我做了一个基于可验证反馈的 Coding Agent 后训练系统。任务来自 SWE-bench，我用自研 Harness 采集轨迹——Agent 和验证器跑在两个隔离容器里，Agent 看不到标答，判决只看官方测试的 returncode。然后我把成功轨迹清洗成 chat 格式，用 QLoRA 微调 Qwen2.5-Coder-7B，只在 assistant token 上算 loss。最后用同一套 Agent 配置对比 Base 和 SFT 的通过率、步数和成本。
>
> 过程中踩过不少坑：pytest 彩色输出导致 gold 被判失败、镜像证书过期、A10 显存不够要分块交叉熵、Docker 虚拟磁盘只增不减。这些都有对应的工程解法。
>
> 下一步是用当前策略采样做拒绝采样，再上 GRPO，最后做 Base/SFT/RL 三方评测，用失败案例反哺数据，形成飞轮。」

---

## 10. GRPO 实现手册（目标方案，落地后可直接作为项目经历）

> 这一节按「完整实现」的粒度写，照着做即可落地。
> 简历措辞见第 11 节，**实测数字用占位符，实现并跑出结果后再替换**。

### 10.1 前提条件（不满足就不要开 GRPO）

| 条件 | 阈值 | 为什么 |
|---|---|---|
| SFT 策略非零成功率 | ≥ 5% | 全 0 时组内 advantage 恒为 0，梯度消失 |
| 每个任务可重复采样 | ≥ 8 条 | GRPO 需要组内比较 |
| 验证器稳定 | gold 能过 | reward 噪声会直接毁掉训练 |
| 单条 rollout 成本可控 | < $0.02 | K=8 × 45 任务 × N 轮，成本会放大 |

**先做 RFT（拒绝采样）验证前提**：用 SFT 策略对训练任务采样 8 次，统计成功率。如果为 0，先扩数据/加训练步数，不要硬上 GRPO。

### 10.2 整体架构：采样与训练分离

```
┌─────────────────────┐        ┌──────────────────────┐
│ Rollout Worker       │        │ Train Worker          │
│ vLLM (LoRA 热加载)   │        │ transformers + peft   │
│ 并发跑 K 条/任务      │        │ 4-bit + checkpointing │
│ 输出 token/logprob   │───────▶│ 计算 GRPO loss        │
│ 调验证容器打分        │  buffer │ 更新 LoRA             │
└─────────────────────┘        └──────────────────────┘
```

**为什么分离**：vLLM 的 PagedAttention 和训练时的 KV/激活内存不能共存于 24GB。采样完一批再训练，显存峰值可控。

### 10.3 Rollout 采样

```python
# 伪代码
for task in train_tasks:
    group = []
    for k in range(K):                      # K=8
        traj = agent.run(task, temperature=1.0, max_steps=40)
        reward = verifier.score(traj.patch)  # 独立容器
        group.append((traj, reward))
    groups.append(group)
```

关键设置：
- **temperature=1.0**（采样多样性；SFT 评测用 0）
- **max_steps=40**，与 SFT 采集一致
- 每条轨迹保存：完整 messages、每步 token ids、policy logprobs、reward
- 组内去重：命令序列完全相同的轨迹只保留一条（否则 advantage 被重复样本稀释）

### 10.4 Reward 设计

```python
def reward(traj, result):
    if result.returncode == 0 and result.n_passed > 0:
        return 1.0
    if result.n_passed + result.n_failed > 0:
        return 0.25 * result.n_passed / (result.n_passed + result.n_failed)  # 部分分
    return 0.0
```

可选的 shaping（要谨慎，容易 reward hacking）：
- 空补丁：-0.1
- 格式错误退出：-0.05
- 超过 40 步：不加分（自然为 0）

**不要**加「改了多少行」「调用了几次工具」这类代理奖励——模型会学会刷指标而不是修 bug。

### 10.5 GRPO 数学与实现

对每个任务的一组 K 条轨迹：

```
r_i        = reward(traj_i)
A_i        = (r_i - mean(r)) / (std(r) + eps)      # 组内归一化
ratio_t    = π_θ(a_t | s_t) / π_old(a_t | s_t)     # 逐 token
L_clip     = min(ratio_t * A_i, clip(ratio_t, 1-ε, 1+ε) * A_i)
L_kl       = KL(π_θ || π_ref)                       # 对 SFT 参考模型
L          = -mean(L_clip) + β * L_kl
```

- `ε = 0.2`，`β = 0.04`（先用默认，再网格）
- `π_ref` 是冻结的 SFT 模型（LoRA 前的基座 + SFT adapter）
- 只对 assistant token 计算 ratio 和 loss（与 SFT 一致）

**实现方式二选一**：

| 方案 | 优点 | 缺点 |
|---|---|---|
| TRL `GRPOTrainer` + 自定义 rollout | 现成 clip/KL/日志 | agentic 多轮需要适配 rollout 接口 |
| 自写 trainer | 完全可控，便于接多轮工具调用 | 要自己实现 logprob 对齐、clip、KL |

推荐先走 TRL，把 agent rollout 包装成「prompt → completion」的形式，reward 函数调验证容器。

### 10.6 训练配置（A10 24GB 实测起点）

| 参数 | 值 |
|---|---|
| 初始化 | SFT LoRA adapter |
| 量化 | 4-bit NF4（与 SFT 一致） |
| LoRA | r=16，仅训练 adapter |
| K（组大小） | 8 |
| batch | 1 任务 × 8 轨迹 / 梯度累积 2 |
| lr | 1e-6（比 SFT 小两个数量级） |
| epochs | 1–2 |
| clip ε | 0.2 |
| KL β | 0.04 |
| max_seq_len | 5888（与 SFT 一致） |
| 采样温度 | 1.0 |
| 评测温度 | 0.0 |

### 10.7 显存与工程

| 问题 | 解法 |
|---|---|
| 采样和训练抢显存 | 分进程：vLLM 采样完关掉，再起训练 |
| 多轮轨迹 logprob 对齐 | 采样时记录每步 token ids + logprobs，训练时用同一 tokenizer 重算 |
| 序列超长 | 与 SFT 相同的分块 CE + 梯度检查点；超长轨迹按消息边界裁剪 |
| 训练慢 | 只更新 LoRA（40M 参数），optimizer 用 paged_adamw_8bit |
| 断点续跑 | 每 N 个任务存一次 adapter + optimizer state |

### 10.8 防 reward hacking

- 验证容器独立、全新，Agent 不挂载任务目录
- 测试补丁只读
- 只跑官方 FAIL_TO_PASS + PASS_TO_PASS ID
- 监控「空补丁率」「格式错误率」「重复命令率」，异常升高说明模型在刷分
- 定期用 held-out 评测集检查，防止过拟合训练任务

### 10.9 评测与指标

| 指标 | 说明 |
|---|---|
| pass@1 | 贪心解码一次通过率（主指标） |
| pass@K | K 次采样至少一次通过（衡量探索能力） |
| 平均步数 | 是否学会高效行动 |
| 空补丁率 / 格式错误率 | 行为健康度 |
| 单任务成本 | token + 容器时间 |
| 训练稳定性 | KL、clip fraction、reward 方差 |

三方对比：Base / SFT / GRPO，同一批 held-out 任务、同一套 Agent 配置。

### 10.10 常见失败模式与调参

| 现象 | 可能原因 | 处理 |
|---|---|---|
| reward 全 0 | 策略太弱 / 任务太难 | 先 RFT、加数据、降难度 |
| reward 全 1 | 任务太简单 / 泄漏 | 检查 held-out 切分、加难度 |
| KL 爆炸 | lr 太大 / β 太小 | lr 降到 5e-7，β 提到 0.1 |
| 输出退化（重复） | 采样温度太低 / clip 太松 | 温度 1.0，ε 0.2 |
| 训练后评测变差 | 过拟合训练任务 | 早停、加 KL、扩任务集 |
| 显存 OOM | K 太大 / 序列太长 | K=4、seq=4096、分块 CE |

### 10.11 预期时间线

```
RFT 验证（采样 + 统计成功率）        0.5 天
GRPO 小规模跑通（5 任务 × K=4）      1 天
全量训练（45 任务 × K=8 × 2 epochs）  2–3 天（A10）
三方评测                              0.5 天
失败案例分析 + 数据反哺                1 天
```

---

## 11. 简历项目描述

### 11.1 当前真实版（现在就能用）

> **基于可验证反馈的 Coding Agent 后训练系统**
> 个人项目 | Python / PyTorch / Transformers / PEFT / Docker / vLLM
>
> - 构建 SWE-bench 任务流水线：从 300 条 Lite 实例中过滤测试 ID 损坏样本，按仓库切分训练/评测集，独立验证「baseline 必失败 + gold 必通过」，得到 45 个可用训练任务。
> - 自研双容器 Harness：Agent 容器不挂载任务目录，验证容器独立应用官方测试，判决只取 pytest returncode，杜绝标答泄漏与嵌套测试污染。
> - 采集 135 条轨迹（45 任务 × 3 rollout），通过率 36%，单条成本 $0.008；清洗后导出 48 条成功轨迹作为 SFT 数据。
> - 在 A10 24GB 上用 QLoRA 微调 Qwen2.5-Coder-7B：4-bit NF4、LoRA r=16、只在 assistant token 上计算 loss，并用分块交叉熵 + 梯度检查点把 7B 训练压进 24GB。
> - 搭建本地 Agent + 远程 vLLM 的评测架构，实现 Base 与 SFT 的同协议对比（通过率 / 步数 / 成本）。

### 11.2 GRPO 落地版（实现并跑出结果后使用）

> **基于可验证反馈的 Coding Agent 后训练系统（SFT + GRPO）**
> 个人项目 | Python / PyTorch / Transformers / PEFT / TRL / vLLM / Docker
>
> - 构建 SWE-bench 任务流水线与双容器 Harness：Agent 容器无标答挂载、验证容器独立跑官方测试，判决只看 returncode；采集 45 个任务、135 条轨迹，通过率 36%，单条成本 $0.008。
> - 用 QLoRA 微调 Qwen2.5-Coder-7B（4-bit NF4 + LoRA r=16 + 分块交叉熵），SFT 后 held-out 通过率从 __% 提升到 __%，空补丁率从 __% 降到 __%。
> - 以官方测试为可验证 reward，实现 GRPO 训练：每任务采样 K=8 条轨迹、组内归一化 advantage、PPO-clip + KL 约束；采样（vLLM）与训练（Transformers）分离，在单卡 A10 24GB 上完成。
> - 设计防 reward hacking 机制：独立验证容器、只读测试补丁、只跑官方测试 ID，并监控空补丁/格式错误/重复命令率。
> - 三方评测（Base / SFT / GRPO）显示 pass@1 从 __% → __% → __%，单任务成本 __，形成「采集 → 清洗 → SFT → RL → 评测 → 失败分析」的数据飞轮。

**填写要求**：所有 `__` 必须是实测数字；跑完评测后从 `data/eval_results/` 和训练日志里取。没有数字的条目删掉，不要留空。

### 11.3 面试时的展开顺序

1. **先讲问题**：Coding Agent 的能力靠可验证反馈，不靠人工标注
2. **再讲系统**：双容器防泄漏 → 轨迹采集 → 清洗 → QLoRA → GRPO
3. **讲取舍**：为什么 GRPO 不用 PPO、为什么采样训练分离、为什么只看 returncode
4. **讲数据**：真实踩过的坑（彩色输出、证书、显存、vhdx）
5. **讲反思**：0% 那轮教会我「区分系统坏了和模型没学会」

### 11.4 不要写进简历的内容

- 没跑过的数字（通过率、成本、提升幅度）
- 没实现的模块（GRPO 没跑通前不要写成已完成）
- 「精通」「主导」这类无法验证的词
- 与岗位无关的技术堆砌（除非面试官追问）
