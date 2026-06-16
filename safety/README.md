# `safety/` — 5 层安全管线（参考实现 / Reference Implementation）

> [!IMPORTANT]
> **这个包不是 Nonull 运行时实际使用的安全层。**
> This package is **NOT** the safety layer the Nonull agent actually uses at runtime.

## 哪个是真正在用的？

Nonull 运行时使用的是 **`core/safety.py` 的 `SafetyGuardian`** —— 一个轻量的 **3 步建议性门控**：

1. 正则黑名单（`block_pattern`）
2. 命令白名单
3. 上下文风险评分（`_evaluate_context_risk` vs `max_risk_score`，默认 0.7）

它在 `core/agent_core.py` 里被 import 和实例化，是 `run()` / `run_react()` / `run_hybrid()` 真正经过的安全检查。

## 那 `safety/` 这个包是什么？

`safety/`（`guardian.py` + `deny_first.py` + `compliance.py`）是一个**更完整的 5 层安全管线参考实现**：

- `PipelineLayer` L1–L5：工具预过滤 → `DenyFirstEngine` 规则 → 风险评分 → 上下文感知 → 动作后检查
- 携带 `SafetyLevel` / ASIL 枚举、`ComplianceChecker`（ISO 26262 / MISRA 模式参考）

它**当前未接入生产 agent 循环** —— 只有测试（`tests/test_safety_*.py`）和 CI smoke-import 引用它。保留它的原因：

1. 它是一个**更丰富的安全架构参考**，展示了 deny-first + 合规检查 + 分层管线的设计；
2. 有完整的单元测试覆盖（`test_safety_guardian.py` / `test_safety_deny_first.py` / `test_safety_compliance.py`）；
3. 未来若要把 agent 的安全层升级到 5 层管线，这里是现成的起点。

## ⚠️ 重要声明

无论 `core/safety.py` 还是 `safety/`，**两者都是建议性（advisory）的** —— 参考 ISO 26262 / MISRA / ASPICE 的**模式与术语**做风险提示，但**不实现** ASIL-D 的抗干扰、MC/DC 覆盖、形式化验证等条款。携带的 `SafetyLevel` / ASIL 枚举是**标签**，不是认证分级。

**请勿将任一安全层用于量产部署、安全关键决策，或替代任何认证安全机制。**

---

*If you're looking for the safety check that actually runs: it's `core/safety.py`. This package is a richer reference design kept for tests and future use.*
