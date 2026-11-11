# 交接文档（2026-11-05）

新开对话时**先读这一份**，它包含全部上下文、当前状态、已知陷阱和后续步骤。
面试叙事、完整技术路线与问答速查见 **`notes/ROADMAP.md`**。

---

## 1. 项目

**RepoRepair-Lab**：基于可验证反馈的 Coding Agent 后训练系统。

| Phase | 内容 | 状态 |
|---|---|---|
| 1 | 跑通 mini-swe-agent，读懂轨迹格式 | ✅ |
| 2 | 自研 Harness（local + docker、验证内嵌、回放） | ✅ |
| 3 | 任务集构建 + 独立验证 + 轨迹采集 | 🟡 试点完成，待全量 |
| 4 | LoRA SFT（Qwen-Coder / TRL） | ✅ 2026-11-07 |
| 5 | 可验证 Reward + GRPO | ⬜ |
| 6 | Base / SFT / RL 统一评测 | ⬜ |

---

## 2. 环境与路径

### 本地开发

```
项目      C:\Users\DELL\Desktop\xiao\亲手微调项目\reporepair-lab
WSL venv  ~/venvs/rrl          （Python 3.12，已装 minisweagent 2.4.6 + reporepair）
上游参考  refs/mini-swe-agent  （只读）
Docker    Docker Desktop + WSL 集成（**每次用前必须确保它已启动**）
```

### 训练服务器

> 连接信息（IP、SSH 密钥路径）不写入仓库：本地放在未跟踪的 `scripts/remote_env.local.sh`，脚本会自动 source 它。

```
SSH       root@<your-server-ip>（密钥路径见本地 remote_env.local.sh）
工作目录  /root/paperArts/bench/           ← 只在这里操作
venv      /root/paperArts/bench/venv       （uv, Python 3.10.12）
代码      /root/paperArts/bench/reporepair-lab/
GPU       A10 24GB / 16 核 / 62GB 内存 / 磁盘剩 115GB
```

⚠️ 这是共享服务器：不要改动工作目录之外的任何文件，**绝不要执行全局 Docker prune**。

---

## 3. 关键代码

| 文件 | 作用 |
|---|---|
| `src/reporepair/harness/agent.py` | `LoopAgent`：主循环 + 钩子 |
| `src/reporepair/harness/reward.py` | 可验证 reward：**只看 returncode**，计数取最后一条摘要 |
| `src/reporepair/harness/environment.py` | local/docker 后端；`mount_task_dir=False` 是防泄漏关键 |
| `src/reporepair/tasks/swebench.py` | 实例解析、镜像名、测试命令、截断 ID 检测 |
| `src/reporepair/tasks/select.py` | 过滤/去重/仓库级切分 |
| `src/reporepair/data/filter.py` | 轨迹过滤、去重、SFT 导出 |
| `scripts/collect.py` | **采集主程序**（双容器、分批拉删、磁盘守卫） |
| `scripts/verify_taskset.py` | 独立验证（baseline 失败 + gold 通过） |
| `scripts/build_train_split.py` | 构建全量训练集（52 条） |
| `scripts/local_collect.sh` | 本地采集入口（加载 .env + venv） |
| `scripts/launch_collect.sh` | tmux 后台启动采集 |

---

## 4. 数据现状

```
data/raw/swebench_lite/test.jsonl      300 条原始
data/taskset/eval.jsonl                20 条（与 eval_verified 同步）
data/taskset/eval_verified.jsonl       20 条 ✅ 已验证（18 sklearn + 2 pytest）
data/taskset/eval_candidates.jsonl     16 条候选（全部验证通过，用了 13 条，剩 3 条备用）
data/taskset/train_full.jsonl          52 条（8 个仓库，完全不含评测仓库）
data/taskset/pilot_seaborn.jsonl       4 条试点
data/trajectories/manifest.jsonl       135 条 rollout（45 个任务完成）
data/trajectories/rejected.jsonl       7 条（gold 无法通过，见下）
```

**2026-11-06 采集完成**：45/52 任务完整（每条 3 个 rollout），135 条轨迹，48 条通过（36%），总成本 $1.12。
无轨迹的 7 条：`psf__requests-2148/2317/2674/3362/863`（httpbin 行为漂移导致 PASS_TO_PASS 失败）、`pydata__xarray-4493`（空输出/超时）、`sphinx-doc__sphinx-8721`（epub 测试断言失败）。
评测镜像（sklearn 5 + pytest 3）已删除，Phase 6 前需重拉。
C 盘采集后 104GB 可用，vhdx 已压缩（26.64→18.63GB）。

任务仓库分布（训练集）：
```
sphinx 14, matplotlib 10, astropy 6, requests 6
xarray 5, pylint 5, seaborn 4, flask 2
```
评测仓库：`scikit-learn`（20 条可用，目前只验证并使用了 5 条）+ `pytest-dev`（7 条，验证了 4 条）。

---

## 5. 试点结果（seaborn 4 条 × 3 rollout）

| 任务 | 成功 | 步数 |
|---|---|---|
| seaborn-2848 | 1/3 | 25/25/21 |
| seaborn-3010 | 1/3 | 8/8/7 |
| seaborn-3190 | 0/3 | 25/25/24（全部打满） |
| seaborn-3407 | 3/3 | 25/18/22 |

```
rollout 成功率 5/12 = 42%
总成本 $0.0821（240 次调用）
单条平均 $0.0068
```

结论：链路正确，成功率与 DeepSeek 公开水平一致。**步数上限已从 25 提到 40**（seaborn-3190 全灭是步数不够）。

---

## 6. 下一步（按顺序）

### ① 清理残留（已完成 2026-11-05）
Docker Desktop 已启动。`mwaskom_1776_seaborn-3407` 残留镜像已删除（清理脚本因权限分类器拦截，改为精确 `docker rmi` 单镜像）。
**同时修复了 `collect.py` 的磁盘守卫**：原 `shutil.disk_usage("/")` 在 WSL 里读到虚拟 1TB 盘（假报 945GB），现改为读 `/mnt/c`（GiB），默认下限提到 50GiB。

### ② 轨迹泄漏复查（已完成）
`grep -rl "gold.patch\|/rrl" data/trajectories/*.traj.json` → clean。

### ③ 全量采集（已完成 2026-11-06）
```bash
wsl -d Ubuntu -- bash "/mnt/c/.../scripts/launch_collect.sh" data/taskset/train_full.jsonl 3 full
```
实际分三轮：`train_full` → 代理故障中止 → `train_remaining`（33 条）→ `train_retry`（8 条）。
最终 45/52 任务、135 条 rollout、通过率 36%、成本 $1.12。

### ④ 评测集扩到 20 条（已完成 2026-11-06）
从原始池筛出 16 条可用 sklearn 候选（另 2 条测试 ID 不可选中被剔除），物化任务目录 → 拉镜像 → `verify_taskset.py` 独立验证（16/16 全部通过）→ 取 13 条合并进 `eval_verified.jsonl`，达到 20 条（18 sklearn + 2 pytest）。
备用未用：`scikit-learn-15535 / 25500 / 25747`。
```bash
python scripts/prepare_eval_expansion.py          # 物化候选
bash scripts/pull_eval.sh                         # 拉镜像
python scripts/verify_taskset.py --split <绝对路径>/data/taskset/eval_candidates.jsonl --out <绝对路径>/data/taskset/verify_report_candidates.json
python scripts/merge_eval_verified.py             # 合并到 20 条
```
⚠️ `verify_taskset.py` 内部 `os.chdir("/")`，`--split`/`--out` 必须传绝对路径。

### ⑤ 清洗 + 导出 SFT（已完成 2026-11-06）
```bash
python scripts/clean_trajectories.py data/trajectories/*/rollout_*.traj.json --out data/clean/sft.jsonl
```
135 条输入 → 保留 48 条 `passed=True`（丢弃 87 条失败），无重复。输出 `data/clean/sft.jsonl`（4.2MB，48 条，平均 41.3 条消息）。
**注意**：导出必须保留 tool 消息的 `tool_call_id`（模型用原生 tool_calls），`filter.py` 已修并加测试。

### ⑥ 同步到服务器并训练（Phase 4 已完成 2026-11-07）
```bash
wsl -d Ubuntu -- bash "/mnt/c/.../scripts/remote_sync.sh"   # 已改为包含 data/clean
```
服务器环境（独立，不碰共享 venv）：
```
/root/paperArts/bench/reporepair-lab/.venv-train     torch 2.5.1+cu124 / transformers 4.57.6 / peft 0.14
/root/paperArts/bench/models/Qwen2.5-Coder-7B-Instruct   14.4GB（ModelScope 下载）
```
训练命令（A10 24GB 实测参数）：
```bash
cd /root/paperArts/bench/reporepair-lab
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
.venv-train/bin/python scripts/train_sft.py \
  --model /root/paperArts/bench/models/Qwen2.5-Coder-7B-Instruct \
  --out outputs/sft-qwen-coder-7b \
  --max-seq-len 5888 --epochs 3 --grad-accum 4
```
结果：37 train / 9 val（超长轨迹按消息边界保留头尾），30 步，14.3 分钟，
train_loss 2.49，eval_loss 0.514 → 0.418 → 0.407。adapter 155MB，已同步回本地 `outputs/sft-qwen-coder-7b/`。

**A10 显存实测**：8192 上下文 OOM，6144 可跑但余量小，最终用 **5888**；CE 必须分块（chunk=512）+ 梯度检查点，否则 fp32 logits 直接爆显存。

### ⑦ 评测 Base vs SFT（Phase 6，2026-11-07 起）
架构：**模型在服务器，Agent 在本地**（本地有 Docker 镜像，服务器没有 GPU 之外的镜像源）。
```
本地 Agent (Docker + mini-swe-agent)
   └─ OpenAI API → localhost:8000 (SSH 隧道)
        └─ 服务器 vLLM (A10) ── base 模型 + sft LoRA adapter
```
服务器：
```bash
# 服务（tmux serve）
bash /root/paperArts/bench/logs/serve.sh
# 内容：vllm serve <model> --served-model-name base --enable-lora \
#   --lora-modules sft=<adapter> --max-model-len 16384 \
#   --enable-auto-tool-choice --tool-call-parser qwen2_xml \
#   --tool-parser-plugin /root/paperArts/bench/logs/qwen2_xml_parser.py
```
本地：
```bash
# 隧道
bash scripts/tunnel_vllm.sh        # ssh -N -L 8000:127.0.0.1:8000
# 评测
bash scripts/run_eval_both.sh      # base 然后 sft，各 20 任务 × 1 rollout
```
结果写 `data/eval_results/{base,sft}/manifest.jsonl`。

**2026-11-07 首轮评测结果**（20 条 × 1 rollout，temperature=0）：

| | base | sft |
|---|---|---|
| 通过 | 0/20 | 0/20 |
| 平均步数 | 0.9（中位 0） | 24.1（中位 31.5） |
| 空补丁 | 16 | 20 |
| 退出状态 | Submitted 14 / FormatError 6 | MaxSteps 8 / FormatError 6 / Error 6 |

结论：**SFT 学会了 Agent 协议（会连续调用工具），但没学会修复技能**——诊断显示它在重复执行相同的 `grep`/`sed` 查看命令，从不编辑文件；base 则多数情况直接提交空补丁。
原因：训练数据只有 37 条、训练仅 30 步，属于链路验证，不是有效的能力提升。
下一步建议：扩大采集（更多仓库/任务/rollout）、过滤掉"重复命令"轨迹、增加训练步数，再复评。

**关键坑**：
- vLLM 0.7.3 是最后一个兼容 torch 2.5.1 / CUDA 12.4 的版本（驱动 550 上限）
- vLLM 需要 setuptools（uv venv 默认没有）
- transformers 必须 `==4.49.0`（5.x 与 vLLM 0.7.3 不兼容）
- vLLM 0.7.3 没有 Qwen2 工具解析器，`scripts/qwen2_xml_parser.py` 是自定义插件，兼容
  `<function .../>`、`<tool_call>`、`<response>`、```json```、裸 JSON、```bash``` 六种格式
- LiteLLM 无法给本地模型算成本，必须 `MSWEA_COST_TRACKING=ignore_errors`
- base 模型经常把命令写在 markdown 代码块里而不是走 tool_calls，解析器兜底处理

---

## 7. 已知陷阱（每一条都真实踩过）

| # | 陷阱 | 现象 | 解法 |
|---|---|---|---|
| 1 | **测试泄漏** | Agent 能看到标答 | Agent 容器不跑 setup；`mount_task_dir=False` |
| 2 | `FAIL_TO_PASS` 是 JSON 字符串 | 88 个 ID 被拆成字符 | `swebench.as_list()` |
| 3 | 测试 ID 含换行/截断 | pytest 说 not found | `has_unselectable_ids()`，括号配平检查；已剔除 25 条 |
| 4 | 嵌套 pytest 摘要污染计数 | gold 全过却判失败 | **判决只看 returncode**，计数取最后一条 |
| 5 | 内联 `wsl bash -lc '...$VAR...'` | 变量被外层展开成空 | 写成脚本文件 |
| 6 | Git Bash 改写 `/mnt/...` 路径 | `C:/Program Files/Git/mnt/...` | `MSYS_NO_PATHCONV=1` |
| 7 | `Path.resolve()` 依赖 cwd | Docker 频繁启停后 `FileNotFoundError` | 启动时 `os.chdir("/")` + 绝对路径 + 增量落盘 |
| 8 | Docker Desktop vhdx 只增不减 | 删镜像后 C 盘不回升 | 已实测：`fstrim` 在 docker-desktop VM 里报 0 B；WSL 稀疏 VHD 被官方禁用（数据损坏风险）；Docker Desktop 正常停止也不压缩。**只能在 Docker 停止后用 diskpart `attach vdisk readonly` + `compact vdisk`（需管理员 UAC）**。采集结束后做一次 |
| 9 | 服务器 DNS 污染 | `registry-1.docker.io` 解析到 Facebook IP | 只能走镜像源或本地拉取 |
| 10 | `docker rmi` 被容器引用时失败 | 镜像残留 | 先删 `minisweagent-*` 容器再重试（已修） |
| 11 | **pytest 彩色输出导致计数解析失败** | gold 全过却判 `gold_should_pass` 失败 | astropy 强制 `--color=yes`，摘要行 `\x1b[1m10 passed` 中 `m` 与 `1` 之间无 `\b`。`reward.py` 已改为解析前 `strip_ansi()`，并让判决严格 `returncode == 0`（2026-11-05 修） |
| 12 | **Clash 代理节点失效** | 所有 docker pull 失败（daocloud 白名单拒绝、1ms 超时） | 代理端口通但上游超时。恢复代理节点后重跑即可，已完成 rollout 自动跳过 |
| 13 | **vhdx 增长吃满 C 盘** | 跑 16 个任务后 101G→46G，镜像已删但空间不回 | 用 `scripts/compact_vhdx.ps1`（停止 Docker → diskpart compact → 重启），实测 79.45→11.24GB、26.64→18.63GB。需要一次 UAC |
| 14 | **SWE-bench 镜像 certifi 过旧** | gold 补丁正确，但 HTTPS 测试报 `CERTIFICATE_VERIFY_FAILED`，整条任务被拒 | 镜像自带 2019 年 certifi。`make_env` 已给容器注入 `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` 指向系统 CA（`/etc/ssl/certs/ca-certificates.crt`），修好后 requests-1963 从全拒变 3/3 通过 |
| 15 | **httpbin 外部服务漂移** | `test_auth_is_stripped_on_redirect_off_host` 报 IndexError（不再返回重定向） | 无法修复，相关 5 条 requests 任务标记为不可用；若将来需要可改用本地 httpbin 容器 |
| 16 | **transformers 5.x 在 Python 3.10 崩溃** | `NameError: name 'nn' is not defined` | 5.x 需要 Python 3.11+。服务器 venv 是 3.10，必须装 `transformers<5`（实测 4.57.6 可用） |
| 17 | **prepare_model_for_kbit_training 把未量化参数转 fp32** | 显存多占 4.4GB，logits 变 fp32 | 调用后手动把 `lm_head` / `embed_tokens` / `model.norm` 转回 bf16 |
| 18 | **A10 24GB 训练 7B 的上下文上限** | 8192 反向传播 OOM | 6144 可跑、5888 稳定；交叉熵必须分块（chunk=512）+ 梯度检查点 |
| 19 | **hf-mirror 大文件只有 ~0.1MB/s** | 模型下载 10 分钟无进展 | 改用 ModelScope（实测 18MB/s）：`https://modelscope.cn/models/Qwen/Qwen2.5-Coder-7B-Instruct/resolve/master/<file>`，wget -c |
| 20 | **hf-mirror 残片续传导致分片损坏** | safetensors `incomplete metadata` | 不要跨源续传；删除后从单一源重下，下载后用 `safe_open` 校验每个分片 |

---

## 8. 常用命令

```bash
# 本地环境
source ~/venvs/rrl/bin/activate
cd "/mnt/c/Users/DELL/Desktop/xiao/亲手微调项目/reporepair-lab"

# 单元测试（15 个）
python -m pytest tests/ -q

# 单任务运行
rrl-run run --task tasks/demo-01-stats --config configs/harness.yaml --backend docker

# 采集（前台调试）
bash scripts/local_collect.sh --split data/taskset/pilot_seaborn.jsonl --rollouts 1 --limit 1

# 采集（后台）
bash scripts/launch_collect.sh data/taskset/train_full.jsonl 3 full

# 汇总
python scripts/summarize_manifest.py
python scripts/summarize_verify.py data/taskset/verify_report.json

# 服务器
MSYS_NO_PATHCONV=1 wsl -d Ubuntu -- bash "/mnt/c/.../scripts/remote_sync.sh"
```

---

## 9. 待决问题

1. **评测集镜像留不留**：留 20 个约 10GB（仍 >100GB）；删掉则评测前需重拉（约 10 分钟）。当前倾向**删掉**，严格遵守"不留镜像"。
2. **全量 rollout 次数**：3 次（约 156 条轨迹，成本约 $1.1）还是 5 次（260 条，约 $1.8）。
3. **SFT 目标模型**：Qwen2.5-Coder-7B-Instruct（A10 24GB，4bit QLoRA 可行）。
4. **是否同时保留失败轨迹**：目前设计只导出成功轨迹；失败轨迹可用于 DPO/拒绝采样，后续再定。
