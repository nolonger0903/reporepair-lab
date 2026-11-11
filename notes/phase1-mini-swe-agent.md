# Phase 1 笔记：mini-swe-agent 源码与轨迹格式

> 上游版本 2.4.6，源码在 `refs/mini-swe-agent`。本文只记录对 RepoRepair-Lab 有用的事实。

## 1. 规模

- `src/` 共 **5349 行**，真正的核心逻辑不到 600 行。
- 没有框架、没有依赖注入容器、没有插件系统。全部靠 Protocol + 鸭子类型。

## 2. 四个核心抽象

| 抽象 | 协议位置 | 实现 | 职责 |
|---|---|---|---|
| `Model` | `src/minisweagent/__init__.py:43` | `models/litellm_model.py:49` | 一次 API 调用，产出 `message` + `extra.actions` |
| `Environment` | `__init__.py:61` | `environments/local.py:19`、`docker.py:45` | 执行一条 bash，返回 `{output, returncode}` |
| `Agent` | `__init__.py:73` | `agents/default.py:38` | 主循环、限流、落盘 |
| `run/*` | — | `run/mini.py:55` | 把三者装配起来 |

装配只有三行（`run/mini.py:99-101`）：

```python
model = get_model(config=config.get("model", {}))
env = get_environment(config.get("environment", {}), default_type="local")
agent = get_agent(model, env, config.get("agent", {}), default_type="interactive")
```

**这就是我们的接缝**：Phase 2 要换掉 Model / Environment / Agent 中的任意一个，只需传自己的类，不用改上游代码。

## 3. 一次运行的数据流

`DefaultAgent.run()`（`default.py:88`）：

```
messages = [system(渲染 system_template), user(渲染 instance_template)]
while True:
    step()                      # = execute_actions(query())
    save(output_path)           # 每步 finally 落盘
    if messages[-1].role == "exit": break
```

`step()` 拆开（`default.py:126-157`）：

1. `query()` — 检查 `step_limit / cost_limit / wall_time_limit`，调 `model.query(messages)`
2. `model.query()` — litellm 调用 → 解析 tool_calls → 把解析结果放进 `extra.actions`
3. `execute_actions()` — 对每个 action 调 `env.execute()`，再用 `observation_template` 渲染成 `role="tool"` 消息
4. 追加回 `messages`

**终止机制**是异常驱动的（`environments/local.py:45`）：

```python
if lines[0].strip() == "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT" and returncode == 0:
    raise Submitted({"role": "exit", "content": submission, "extra": {...}})
```

`Submitted`、`LimitsExceeded`、`TimeExceeded`、`FormatError`、`InterruptAgentFlow` 都是 `InterruptAgentFlow` 的子类，在 `run()` 里被捕获后追加 exit 消息。

## 4. 配置系统

三层递归合并（`config/__init__.py:56`）：

```
内置 mini.yaml  ←  -c my.yaml  ←  -c key=value  ←  CLI 参数
```

- 模板是 **jinja2**，`StrictUndefined`，缺变量直接报错。
- 模板变量来自 `get_template_vars()`（`default.py:52`）：agent 配置 + env + model + `system/release/version/machine` + `task`。
- 所以提示词完全可以按配置改，不用改代码。

## 5. 轨迹格式（关键）

文件顶层只有三个键：

```json
{
  "info": {
    "model_stats": {"instance_cost": 0.0011, "api_calls": 5},
    "config": {"agent": {...}, "model": {...}, "environment": {...}},
    "mini_version": "2.4.6",
    "exit_status": "Submitted",
    "submission": ""
  },
  "messages": [...],
  "trajectory_format": "mini-swe-agent-1.1"
}
```

单条消息：

| role | 字段 | 说明 |
|---|---|---|
| `system` | `content` | 系统提示 |
| `user` | `content` | 渲染后的任务说明 |
| `assistant` | `content`, `tool_calls`, `extra.actions`, `extra.cost`, `extra.response`, `extra.timestamp` | `extra.response` 是 litellm 原始响应，**含完整 usage** |
| `tool` | `content`, `extra.returncode`, `extra.exception_info`, `extra.raw_output` | `content` 是渲染后的 observation |
| `exit` | `content`, `extra.exit_status`, `extra.submission` | 终止标记 |

### 对 SFT 的直接可用性

- 训练样本就是 `messages[:k]` → 预测 `messages[k]`，标准 chat 格式，**无需转换**。
- 但要注意两点：
  1. `extra.response` 里带 `usage`、`cost`，训练前必须剥离，否则 tokenizer 会把它当文本。
  2. `tool` 消息是**文本渲染**后的结果（`observation_template`），不是结构化 tool result —— 微调时模型看到的就是这个文本，保持一致即可。
- 成本已被记录（本例 5 次调用 $0.0011），可以直接按 cost 过滤轨迹。

### 实测样本（demo-01-stats）

```
[ 0] system    chars=62
[ 1] user      chars=3133
[ 2] assistant chars=91   → 2 个 bash 调用（ls / pytest）
[ 3] tool      chars=1484
[ 4] tool      chars=1591
[ 5] assistant chars=41   → nl -ba 读两个文件
[ 6] tool      chars=2279
[ 7] assistant chars=132  → python 脚本原地改写 stats.py
[ 8] tool      chars=955
[ 9] assistant chars=57   → pytest + 边界用例自测
[10] tool      chars=137
[11] tool      chars=52
[12] assistant chars=217  → echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
[13] exit      chars=0
```

5 次模型调用，7 个测试全过，diff 精确命中两处 bug（`sorted(xs)` 与 `len(xs)-1`）。

## 6. 上游的三个不足（也就是我们的机会）

1. **`submission` 常常是空的**。`echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` 不带任何摘要，`_check_finished` 取 `lines[1:]` 得到空串。作为训练信号，缺少"模型自述改了什么"的正样本。→ Phase 2 改成交互式结构化提交。
2. **没有验证钩子**。测试跑没跑、过了没过，Harness 完全不知道，只能事后外部跑。→ Phase 2/5 的 Verifiable Reward 必须内嵌到 Harness 里。
3. **无轨迹回放**。轨迹只存不读。→ Phase 2 要做 replay，才能做确定性复现和反事实分析。

## 7. 结论

Phase 1 目标达成：**跑通 + 读懂 + 拿到第一条真实轨迹**。

对后续的直接输入：

- Phase 2 的 Harness 用 `Protocol` 兼容方式扩展，不 fork 上游。
- Phase 3 的任务格式沿用 `repo + tests + task.md + git 基线`。
- Phase 4 的 SFT 数据 = 剥掉 `extra` 的 `messages`。
