# Phase 2-3 笔记：Harness、任务集与数据清洗

## Phase 2：Harness

### 为什么复用上游而不是 fork

`minisweagent.Model` 和 `minisweagent.Environment` 是 Protocol，我们直接接入：

```python
from minisweagent.models.litellm_model import LitellmModel
from minisweagent.environments.docker import DockerEnvironment
```

只有 `LoopAgent` 是我们自己的。好处：上游修 bug / 加模型时不用跟进；坏处：受上游消息格式约束——但那个格式正好是训练能用的。

### 补上的三个缺口

| 上游问题 | 我们的做法 |
|---|---|
| `submission` 为空 | 提示词要求 `printf 'MARKER\n<摘要>'`，环境逻辑天然取第二行起 |
| 验证不内嵌 | `verifier` 回调 + `--verify-every N`，每步记录 `VerifyResult` |
| 无法回放 | `trajectory.replay()`：reset 到基线后逐条重放，比对 returncode |

### 异常语义

`LoopAgent.run()` 统一收口：

```
Submitted          → exit_status="Submitted"，取 submission
LimitsExceeded     → cost/step 超限
FormatError        → 模型没按工具调用格式输出
InterruptAgentFlow → 其他中断
其他 Exception      → exit_status=<异常类名>，轨迹仍落盘
```

最后无论如何跑一次 `verifier()` 算 final reward。

### 验证器

`reward.verify(env, test_command)`：

- 解析 pytest 摘要行 (`N passed` / `M failed` / `k errors`)
- **二值 reward**（全过=1.0）作为训练信号
- 部分分 `0.25 * passed/(passed+failed)` 只用于分析，不进 RL
- 判定条件：`returncode==0 and 有测试运行 and 无失败`

## Phase 3：任务集

### 流水线

```
SWE-bench Lite 300
  → filter_pool(repos=PYTEST_REPOS, 200..6000 chars)  → 104
  → dedup(Jaccard > 0.85, 同仓库)                      → 104 (-0)
  → split_by_repo(eval_ratio=0.25, seed=0)             → train 67 / eval 37
  → stratified_sample                                  → 22 / 8
  → materialize                                        → 30 个任务目录
```

评测仓库：`pytest-dev/pytest`、`scikit-learn/scikit-learn`（整仓隔离）。

### 与上游 SWE-bench 的对接点

- 镜像名：`swebench/sweb.eval.x86_64.<instance_id>`，`__` → `_1776_`
- 容器工作目录：`/testbed`
- 环境：conda env `testbed`（激活是 best-effort，部分镜像已在 PATH 上）
- 测试执行：把 FAIL_TO_PASS + PASS_TO_PASS 的 node id 用 base64 编码进命令，规避引号问题

### 踩过的坑（独立验证抓出来的，共 4 个）

**1. `FAIL_TO_PASS` 是字符串不是列表。** 数据集里存的是 `'["a::b", "c::d"]'`。第一版直接 `list()`，把 88 个 node id 拆成了 3000 多个字符。修复见 `swebench.as_list()`。

**2. 测试 ID 里可能有换行符。** 参数化用例的 ID 会带多行 diff 文本。用 `"\n".join(ids)` 拼再 split 会被拆断。改用 `base64(json.dumps(ids))`，JSON 能无损往返。

**3. 数据集里有被截断的转义 ID。** 少数 ID 形如 `...[left0-right0-\n]`（字面量反斜杠+n），是当年从多行 pytest 输出按行解析时截断的产物；容器里真实 ID 更长，永远选不中。`has_unselectable_ids()` 检测并剔除，本次剔除 2 条。

**4. 嵌套 pytest 的摘要污染计数（最隐蔽）。** pytest 自己的测试套件会用 `pytester` 在子进程里再跑 pytest，那些 `N passed / M failed` 也会进入日志。原来把所有匹配求和，导致 gold patch 明明全过（returncode=0）却被判为 32 个失败。

修复：**判定只看 returncode**，计数只取**最后一条**摘要（顶层运行的那条）。这条教训很关键——评测器的判决信号必须单一、可靠，不能靠文本统计。

### 第一条通过的独立验证

`pytest-dev__pytest-5692`：

```
baseline (test.patch only)  → FAILED   ✔ 证明 bug 真实存在
gold.patch applied          → 70 passed, returncode=0  ✔ 证明任务可解
ok=True
```

### 去重阈值实测

同仓库 746 对样本，最高 Jaccard **0.54**，>0.6 的 0 对。当前阈值 0.85 安全但几乎不生效；正式扩量时降到 0.6 才有区分度。

## 数据清洗

`data/filter.py`：

- `filter_trajectories(require_pass, allowed_status, max_cost, max_steps)` → 返回保留集 + 丢弃原因计数
- `dedup_trajectories()` → 命令序列 SHA1 签名，同签名保留成本最低的
- `to_sft_messages()` → 剥离 `extra`，**丢弃 `exit` 消息**
- `export_sft()` → `{task_id, reward, messages}` JSONL

为什么丢 `exit`：它是 harness 的终止标记，不是模型生成的 token。把它当训练目标会让模型学会输出一个它从未生成过的角色。

## Docker 环境记录

- 使用 Docker Desktop 的 WSL 集成（不用原生安装）
- **Docker Desktop 必须处于运行状态**，否则 WSL 里 `/mnt/wsl/docker-desktop` 不存在、`docker` 是断链
- 镜像 `python:3.12-slim` 挂载中文路径正常
- 首次 `docker run` 若镜像未拉取会返回 125，先 `docker pull`
- 容器内 pip 走清华源

### 环境陷阱：命令行里的 `$变量` 会被提前展开

通过 `wsl -d Ubuntu -- bash -lc '...'` 内联执行时，命令里的 `$var` 会在到达 WSL 之前被外层 shell 展开成空串，导致循环/变量赋值静默失效。

```bash
# 错误：img 是空串，docker pull 报 invalid reference format
wsl -d Ubuntu -- bash -lc 'img="x:$id"; docker pull "$img"'

# 正确：写进脚本文件，脚本内的变量不受影响
python scripts/pull_images.py   # 或 bash scripts/xxx.sh
```

凡是带变量、循环、引号嵌套的复杂命令，一律写成脚本文件再执行。

### 环境陷阱：Git Bash 会改写 `/mnt/...` 路径

把 Linux 路径当作 `wsl` 的**裸参数**传入时，Git Bash 会把它转换成 Windows 路径：

```bash
wsl -d Ubuntu -- bash /mnt/c/.../verify_eval.sh
# → bash: C:/Program Files/Git/mnt/c/.../verify_eval.sh: No such file or directory

MSYS_NO_PATHCONV=1 wsl -d Ubuntu -- bash /mnt/c/.../verify_eval.sh   # 正确
```

路径写在 `bash -lc '...'` 的引号内则不受影响。

### 环境陷阱：`Path.resolve()` 在容器频繁启停时会失败

`pathlib.Path.resolve()` 内部调用 `os.getcwd()`，而项目目录位于 `/mnt/c`。批量跑 Docker 容器期间，该挂载点的目录句柄会瞬时失效，`getcwd()` 抛 `FileNotFoundError`，表现为：

```
FileNotFoundError: [Errno 2] No such file or directory   ← 指向 resolve()/realpath()/abspath()
```

修法（`scripts/verify_taskset.py`）：

```python
os.chdir("/")            # 启动即切断对 /mnt/c 工作目录的依赖
paths = [p.resolve() for p in ...]   # 之后只用绝对路径
_write_report(out, results)          # 每完成一条就落盘，崩溃不丢结果
```

一般原则：长时间批量任务不要依赖 cwd，且要增量落盘。
