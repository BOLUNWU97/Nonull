# 多模型混合调度 + 多智能体协同 — 集成指南

> Nonull 的 `multimodel/` 包:多厂商模型统一接入 + 智能路由 + 多模型协作。
> 这是继 `run()`(结构化循环)、`run_react()`(ReAct 循环)之后的第三种执行模式 `run_hybrid()`。

---

## 1. 整体改造架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          Nonull Agent                            │
│  run()  结构化五阶段   run_react()  ReAct循环   run_hybrid() ← 新 │
└───────────────────────────────┬─────────────────────────────────┘
                                │ run_hybrid(task)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  HybridScheduler (统一门面)                       │
│         from_config(config) → 复用 Nonull 的 CostTracker          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐      ┌────────────────┐     ┌──────────────────┐
│  TaskRouter   │      │ ModelDispatcher│     │MultiModelCollab- │
│  智能路由调度  │      │  调用封装层     │     │ orator 协作层    │
│               │      │                │     │                  │
│ 分类:         │      │ 多Key轮询       │     │ 1.拆解子任务      │
│ 简单/复杂/    │─────▶│ 失败重试        │◀───▶│ 2.并行执行        │
│ 超复杂/隐私    │      │ 负载均衡        │     │ 3.交叉校验        │
│               │      │ 模型降级        │     │ 4.汇总整合        │
│ 策略:         │      │ 调用日志        │     │                  │
│ 质量/成本/速度 │      │                │     │ (仅超复杂任务)    │
└───────┬───────┘      └────────┬───────┘     └────────┬─────────┘
        │                       │                       │
        └───────────────────────┼───────────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ModelRegistry (模型管理层)                      │
│  ModelEntry × N + KeyRotator × N (每模型一个多Key轮询器)          │
└───────────────────────────────┬─────────────────────────────────┘
                                │ 复用 core.llm_client.LLMClient (纯 httpx)
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   ┌─────────┐            ┌──────────┐           ┌────────────┐
   │ 云端 API │            │ 本地部署  │           │ LiteLLM 网关│
   │ OpenAI   │            │ Ollama   │           │ (可选, 统一 │
   │ Claude   │            │ LM Studio│           │ 所有厂商)   │
   │ DeepSeek │            └──────────┘           └────────────┘
   │ 通义千问 │
   └─────────┘
```

**核心设计取舍:**
- **不强依赖 LiteLLM**。项目已有的 `LLMClient` 是纯 httpx 打 OpenAI 兼容端点,而 Ollama/LM Studio/DeepSeek/通义千问(兼容模式)/LiteLLM/vLLM **都暴露 OpenAI 兼容 `/chat/completions`**。所以一个 client 类即可覆盖全部。
- **两种部署模式**:(A) 直连——每个模型配自己的 base_url+keys;(B) LiteLLM 网关——所有模型 base_url 指向 `localhost:4000`,厂商差异/重试/负载均衡交给 LiteLLM。代码零改动,只换配置。
- **每个模型一个 KeyRotator**——多 Key 轮询 + 429/401 时冷却跳过,实现 Key 级负载均衡。

---

## 2. 模型配置

### 2A. 直连模式 — `multimodel/nonull_models.yaml`

```yaml
models:
  reasoner:                         # 强模型 (复杂任务)
    model_id: deepseek-reasoner
    provider: deepseek
    base_url: https://api.deepseek.com/v1
    api_keys: [${DEEPSEEK_API_KEY_1}, ${DEEPSEEK_API_KEY_2}]  # 多Key轮询
    tier: large
    priority: 100
  fast-mini:                        # 小模型 (简单任务)
    model_id: gpt-4o-mini
    provider: openai
    base_url: https://api.openai.com/v1
    api_keys: [${OPENAI_API_KEY_1}]
    tier: small
  local-llama:                      # 本地模型 (隐私强制)
    model_id: llama3.1
    provider: ollama
    base_url: http://localhost:11434/v1
    api_keys: ["ollama"]
    tier: local
    is_local: true
    privacy: internal

routing:
  strategy: balanced                # quality | cost | speed | balanced
  force_local_on_privacy: true      # 内网/机密数据强制本地
```

完整示例(含 Claude/通义千问/LM Studio + 成本/延迟标注)见 `multimodel/nonull_models.yaml`。

### 2B. LiteLLM 网关模式 — `multimodel/litellm_config.yaml`

```bash
pip install litellm[proxy]
litellm --config multimodel/litellm_config.yaml --port 4000
```

然后把 `nonull_models.yaml` 里所有 `base_url` 改成 `http://localhost:4000`,`api_keys` 填 LiteLLM master key 即可。LiteLLM 自动处理多 Key 负载均衡、失败降级、响应缓存、成本预算。完整 config 见 `multimodel/litellm_config.yaml`。

---

## 3. 智能任务分类路由逻辑

`TaskRouter.classify_complexity()` 用零成本启发式分类:

| 信号 | 判定 |
|---|---|
| 代码特征(```` ``` ````/`def`/`class`/`import`) | 复杂 |
| 文本 > 1500 字符 | 复杂 |
| 复杂关键词(分析/设计/方案/推理/调试…)占优 | 复杂 |
| 超复杂信号(全面/端到端/完整方案) + 多复杂信号 | 超复杂 → 触发协作 |
| 短文本(<200)+ 简单关键词(翻译/问答/闲聊) | 简单 |
| 隐私关键词(内网/机密/不要外传) | 强制本地模型 |

```python
from multimodel import TaskRouter, ModelRegistry, RoutingStrategy

router = TaskRouter(registry, default_strategy=RoutingStrategy.BALANCED,
                    force_local_on_privacy=True)
decision = router.route("帮我设计一个分布式限流方案")
# decision.model        → 强模型
# decision.complexity   → super_complex
# decision.needs_collaboration → True
# decision.to_dict()    → 完整决策日志
```

策略覆盖:`router.route(task, strategy=RoutingStrategy.COST)` 选最便宜的合格模型;`SPEED` 选延迟最低;`QUALITY` 选 priority 最高。

---

## 4. 单模型自动分发调用

`ModelDispatcher.dispatch()` —— 多 Key 轮询 + 重试 + 降级 + 日志:

```python
from multimodel import ModelDispatcher
from core.llm_client import LLMMessage

dispatcher = ModelDispatcher(registry, cost_tracker=agent._cost_tracker, max_retries=2)
result = dispatcher.dispatch(
    registry.get("reasoner"),
    [LLMMessage(role="user", content="解释快速排序")],
    json_mode=False,
    allow_fallback=True,   # 失败自动降级到备选模型
)
print(result.content)              # 模型输出
print(result.log.to_dict())        # 调用日志: 用了哪个Key/重试几次/延迟/成本
print(dispatcher.call_logger.summary())  # 全局: 成功率/各模型调用次数/总成本
```

容错行为:
- **429 限流** → 冷却该 Key(按 Retry-After)+ 换下一个 Key 重试
- **401/403 认证失败** → 该 Key 冷却 1 小时 + 换 Key
- **5xx 服务错误** → 指数退避重试
- **重试耗尽** → 降级到同档位/medium 档备选模型(`allow_fallback=True`)

---

## 5. 复杂任务多模型并行协作

`MultiModelCollaborator.collaborate()` —— 拆解 → 并行 → 交叉校验 → 汇总:

```python
from multimodel import MultiModelCollaborator

collab = MultiModelCollaborator(registry, router, dispatcher,
                                enable_cross_check=True, max_parallel=4)
result = await collab.collaborate("设计一个完整的分布式限流系统")

print(result.final_output)         # 整合后的最终方案
print(result.to_dict())            # 各子任务用了哪个模型/是否被校验
# result.subtasks      → 拆解的子任务列表
# result.total_models_used → 协作用了几个模型
# result.cross_checked → 是否做了交叉校验
```

4 阶段流水线:
1. **DECOMPOSE** — 强模型把任务拆成 2-5 个独立子任务(JSON)
2. **PARALLEL** — 每个子任务独立路由 + 并行执行(按依赖拓扑分层,`asyncio.gather`)
3. **CROSS_CHECK** — 每个子结果让**不同的**模型审查纠错(交叉校验)
4. **SYNTHESIZE** — 汇总模型整合所有子结果,解决矛盾,产出最终答案

简单任务**不进此层**(单模型独立执行,避免资源浪费)。

---

## 6. 接入原有智能体(已完成)

集成已落地到 `core/agent_core.py`,Nonull 现在有第三种执行模式:

```python
from core.agent_core import Nonull

# config 需含 models.* 段 (load_yaml multimodel/nonull_models.yaml)
agent = Nonull(config=my_config)

# 模式 3: 混合调度 (自动路由 + 超复杂协作)
result = await agent.run_hybrid("帮我设计一个分布式限流方案")
print(result["schedule_mode"])   # "single" | "collaboration"
print(result["model_used"])      # 用了哪个/几个模型
print(result["complexity"])      # simple | complex | super_complex
print(result["output"])          # 最终输出

# 策略覆盖
await agent.run_hybrid("翻译: hello", strategy="speed")        # 速度优先
await agent.run_hybrid("处理内网数据", privacy="internal")      # 强制本地
await agent.run_hybrid("写个函数", force_single=True)           # 跳过协作
```

**接入做的改动**(全部完成,零回归,834 测试全绿):
1. 新增 `multimodel/` 包(registry/router/dispatcher/collaborator/scheduler)
2. `Nonull.__init__` 加 `self._hybrid_scheduler = None`
3. `Nonull.hybrid_scheduler` property —— 惰性从 config 构建 HybridScheduler,复用实例的 CostTracker
4. `Nonull.run_hybrid()` —— 第三种模式,与 run/run_react **同实例、同成本追踪、同记忆(召回+存储)、统一返回格式**(status/output/mode/cost + schedule_mode/model_used/complexity)

**接入新模型**:编辑 `nonull_models.yaml` 的 `models:` 段加一条,无需改代码。

---

## 7. 常见报错与优化方案

| 报错 / 现象 | 原因 | 解决 |
|---|---|---|
| `ModelRegistry 为空, 无可路由模型` | config 没 models 段 | `config.load_yaml("multimodel/nonull_models.yaml")` |
| 隐私任务降级到云端 + warning | 无本地模型可用 | 配置 Ollama/LM Studio 本地模型,或关 `force_local_on_privacy` |
| 本地模型 `Connection refused` | Ollama/LM Studio 没启动 | `ollama serve` / 启动 LM Studio server;确认端口(11434/1234) |
| 429 频繁 + 调用慢 | 单 Key 配额不足 | 配多个 `api_keys`(KeyRotator 自动轮询) |
| 所有调用记为 "unknown" model 成本 | model_id 不在 CostTracker 价格表 | `cost_tracker.register_price(model_id, in, out)` |
| 协作任务超时 | 子任务太多/串行依赖 | 调小 `max_parallel`,减少 depends_on 链 |
| 通义千问 400 错误 | 用了原生端点 | 必须用 compatible-mode 端点 `dashscope.aliyuncs.com/compatible-mode/v1` |
| 简单任务也走了强模型 | 分类阈值不合适 | 调 `router.complex_char_threshold`,或加简单关键词 |

**性能优化:**
- **响应缓存**:LiteLLM 网关模式开 `cache: true`,相同请求直接命中,省成本
- **连接复用**:ModelDispatcher 缓存 (模型,Key) → LLMClient,复用 httpx 连接池
- **本地优先**:把 Ollama 小模型 priority 调高,简单任务零成本
- **成本预算**:LiteLLM `max_budget` 全局守卫;或 Nonull CostTracker 设 budget
- **延迟优化**:超复杂任务 `max_parallel` 调大,子任务真并行

---

## 模块清单

| 文件 | 职责 |
|---|---|
| `multimodel/registry.py` | ModelRegistry + ModelEntry + KeyRotator(模型管理层) |
| `multimodel/router.py` | TaskRouter(智能路由调度层) |
| `multimodel/dispatcher.py` | ModelDispatcher + CallLogger(调用封装层) |
| `multimodel/collaborator.py` | MultiModelCollaborator(多模型协作层) |
| `multimodel/scheduler.py` | HybridScheduler(统一门面) |
| `multimodel/litellm_config.yaml` | LiteLLM 网关配置(模式 B) |
| `multimodel/nonull_models.yaml` | Nonull 模型注册配置(模式 A) |
| `tests/test_multimodel.py` | 24 单元测试(全绿) |
