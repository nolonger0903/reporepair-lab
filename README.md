# RepoRepair-Lab

基于可验证反馈的 Coding Agent 后训练系统。

目标：让模型在真实代码库里修 bug，并用**测试结果**而不是人工判断来验收和打分。

---

## 四层架构

```
┌──────────────────────────────────────────────────────────┐
│ 1. 文件层：Windows 磁盘                                   │
│    C:\Users\DELL\Desktop\xiao\亲手微调项目                │
│    你编辑、查看代码的地方                                 │
└──────────────────────┬───────────────────────────────────┘
                       │ WSL 挂载为 /mnt/c/...
                       ▼
┌──────────────────────────────────────────────────────────┐
│ 2. 我们的执行层：WSL2 Ubuntu (~/venvs/rrl)                │
│    LoopAgent 主循环、调用 DeepSeek、解析轨迹、算 reward   │
└──────────────────────┬───────────────────────────────────┘
                       │ env.execute({"command": ...})
                       ▼
┌──────────────────────────────────────────────────────────┐
│ 3. Agent 命令层：Docker 容器                              │
│    模型生成的 bash、测试套件都在这里跑（隔离、可复现）    │
└──────────────────────┬───────────────────────────────────┘
                       │ Phase 4 起
                       ▼
┌──────────────────────────────────────────────────────────┐
│ 4. 训练层：A10 服务器                                     │
└──────────────────────────────────────────────────────────┘
```

为什么每层都存在：

- **WSL**：模型生成的是 Linux 命令（`sed -i`、heredoc、`nl -ba`），Windows 上跑不了；训练栈也只支持 Linux；生产环境是 Linux 服务器。
- **Docker**：Agent 会执行任意生成的命令——隔离保护 API Key 和本机文件；SWE-bench 各仓库依赖冲突，必须一镜像一任务；同一镜像保证评测可复现。

---

## 目录

```
reporepair-lab/
├── src/reporepair/
│   ├── harness/        # Agent 循环、执行环境、验证、轨迹
│   │   ├── protocol.py     # TaskSpec / StepRecord / Trajectory / VerifyResult
│   │   ├── agent.py        # LoopAgent（复用上游 Model，自研控制流）
│   │   ├── environment.py  # local / docker 双后端
│   │   ├── reward.py       # 跑测试 → 可验证 reward
│   │   └── trajectory.py   # 回放 + 差异比对
│   ├── tasks/          # SWE-bench 实例、过滤/去重/切分/采样
│   ├── data/           # 轨迹清洗与 SFT 导出
│   ├── reward/         # （Phase 5）
│   ├── train/          # （Phase 4）
│   ├── eval/           # （Phase 6）
│   └── cli.py          # rrl-run run / replay
├── configs/            # 提示词与运行配置
├── tasks/              # 任务集
│   ├── demo-01-stats/      # 自建演示任务（git 基线可 diff）
│   └── swebench/           # 30 条从 SWE-bench Lite 物化
├── scripts/            # 数据获取、任务集构建、验证、清洗
├── data/               # 数据产物（不入库）
├── tests/              # 单元测试
└── notes/              # 实验与源码笔记
```

---

## 快速开始

```bash
# WSL 内
source ~/venvs/rrl/bin/activate
cd /mnt/c/Users/DELL/Desktop/xiao/亲手微调项目/reporepair-lab

# 克隆后首次运行 demo 任务前，先恢复其 git 基线（嵌套 .git 不入库）
bash tasks/demo-01-stats/setup.sh

# 在演示任务上跑一次（本地后端）
rrl-run run --task tasks/demo-01-stats --config configs/harness.yaml \
  --verify-every 2 --output data/demo.traj.json

# 同样的任务，Docker 隔离后端
rrl-run run --task tasks/demo-01-stats --config configs/harness.yaml \
  --backend docker --verify-every 2 --output data/demo-docker.traj.json

# 回放一条轨迹，对比 returncode
rrl-run replay --task tasks/demo-01-stats --trajectory data/demo.traj.json

# 清洗轨迹并导出 SFT 数据
python scripts/clean_trajectories.py data/*.traj.json --out data/clean/sft.jsonl
```

任务集构建：

```bash
python scripts/fetch_swebench.py                  # 下载 SWE-bench Lite
python scripts/build_taskset.py --n 30 --seed 0   # 过滤→去重→切分→采样→物化
python scripts/verify_taskset.py                  # 独立验证（需 Docker）
```

---

## 当前进度

| Phase | 内容 | 状态 |
|---|---|---|
| 1 | 跑通 mini-swe-agent，读懂轨迹格式 | ✅ |
| 2 | 自研 Harness：local + docker、验证内嵌、回放 | ✅ |
| 3 | 任务集 + 数据清洗 + 独立验证 + 轨迹采集 | 🟡 试点 12 条通过，待全量 52 条 |
| 4 | LoRA SFT（Qwen-Coder / TRL） | ⬜ |
| 5 | 可验证 Reward + GRPO + 多轮 rollout | ⬜ |
| 6 | Base / SFT / RL 统一评测 | ⬜ |

> 详细的当前状态、环境路径、已知陷阱与后续步骤见 **[notes/HANDOFF.md](notes/HANDOFF.md)**。

---

## 设计要点

1. **不 fork 上游**。`minisweagent.Model` 和 `Environment` 通过 Protocol 接入，上游升级不影响我们。
2. **验证内嵌**。`--verify-every N` 在循环内跑测试，记录"第几步开始通过"，这是轨迹质量分析的核心信号。
3. **结构化提交**。`printf 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n<摘要>'`，解决上游 submission 为空的问题。
4. **仓库级切分**。训练集和评测集不共享任何仓库，杜绝泄漏。
5. **SFT 导出剥离脚手架**。`extra` 字段和 `exit` 消息不进入训练数据。
