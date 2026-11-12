# RepoRepair-Lab

基于可验证反馈的 Coding Agent 后训练系统。

目标：让模型在真实代码库里修 bug，并用**测试结果**而不是人工判断来验收和打分。

---

## 架构

- **Harness**：控制 Agent 循环，执行模型生成的命令，回填观测，记录完整轨迹。
- **隔离执行**：Agent 容器不挂载任务目录，看不到标准答案；判分在全新容器里应用 Agent patch 和官方测试补丁。
- **后训练**：成功轨迹清洗成 chat 格式，用 QLoRA 微调 Qwen2.5-Coder-7B。
- **评测**：同一套 Harness 和判分流程，对比 Base / SFT / RL 的通过率、步数、成本。

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
│   ├── tasks/          # SWE-bench 实例解析、过滤/去重/切分
│   ├── data/           # 轨迹清洗与 SFT 导出
│   └── cli.py          # rrl-run run / replay
├── configs/            # 提示词与运行配置
├── tasks/              # 任务集（demo + SWE-bench 物化任务）
├── scripts/            # 采集、任务集构建、验证、清洗、训练、评测
├── tests/              # 单元测试
└── notes/              # 实验记录与交接文档
```

`data/` 和 `outputs/` 是运行产物，不入库。

---

## 快速开始

```bash
# Linux / WSL（Docker 后端需先启动 Docker）
git clone https://github.com/nolonger0903/reporepair-lab.git
cd reporepair-lab
python -m venv .venv && source .venv/bin/activate
pip install -e .

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

任务集构建与采集：

```bash
python scripts/fetch_swebench.py                  # 下载 SWE-bench Lite
python scripts/build_taskset.py --n 30 --seed 0   # 过滤→去重→切分→采样→物化
python scripts/verify_taskset.py                  # 独立验证（需 Docker）
python scripts/collect.py                         # 双容器采集轨迹
```

---

## 当前进度

| Phase | 内容 | 状态 |
|---|---|---|
| 1 | 跑通 mini-swe-agent，读懂轨迹格式 | ✅ |
| 2 | 自研 Harness：local + docker、验证、回放 | ✅ |
| 3 | 任务集 + 独立验证 + 轨迹采集 | ✅ 52 条训练任务中 45 条可用，135 条轨迹，通过率 36% |
| 4 | QLoRA SFT（Qwen2.5-Coder-7B） | ✅ 30 步，eval_loss 0.407 |
| 5 | 可验证 Reward + GRPO | ⬜ 下一步 |
| 6 | Base / SFT / RL 统一评测 | 🟡 首轮 Base / SFT 评测完成（均 0/20，链路已验证） |

> 第一轮结论：链路通了，能力还没出来。Base 平均 0.9 步（直接交空补丁），SFT 平均 24 步（学会了连续调工具，但不会编辑文件）。问题在训练量，不在系统。
>
> 详细的当前状态、已知陷阱与后续步骤见 **[notes/HANDOFF.md](notes/HANDOFF.md)**。

---

## 设计要点

1. **不 fork 上游**。`minisweagent.Model` 和 `Environment` 通过 Protocol 接入，上游升级不影响我们。
2. **验证可内嵌**。`--verify-every N` 在循环内跑测试，记录"第几步开始通过"；正式采集的最终判分放在独立容器里，保证 Agent 无法污染评测。
3. **结构化提交**。`printf 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\n<摘要>'`，解决上游 submission 为空的问题。
4. **仓库级切分**。训练集和评测集不共享任何仓库，杜绝泄漏。
5. **SFT 导出剥离脚手架**。`extra` 字段和 `exit` 消息不进入训练数据。
