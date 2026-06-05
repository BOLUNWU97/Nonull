# Nonull 智驾智能体

> **有性格、有记忆、有安全意识、能自我成长的智驾 AI 工程师**
> A self-evolving AI engineer for autonomous driving — with personality, memory, and safety awareness.

---

## 一句话认识 Nonull

Nonull 是专为**智能驾驶行业**设计的 AI 智能体。

你告诉它做什么，它自己想办法搞定。搞定一次之后，下次它会做得更好。

```
"帮我审查这个 AEB 模块的代码"
     → Nonull 检查 MISRA 规范、找 bug、提优化建议

"对紧急制动系统做 HARA 安全分析"
     → Nonull 按 ISO 26262 标准分析，给出 ASIL 等级

"生成雨天夜间行人横穿场景"
     → Nonull 生成标准 OpenSCENARIO 场景文件
```

---

## 它和别的 AI 有什么不一样？

| 别的 AI | Nonull |
|---------|--------|
| 聊完就忘 | 🧠 **有记忆** — 四种记忆，1B Token 容量 |
| 你说啥它做啥 | 🛡️ **有安全** — 五关检查，不安全的事不做 |
| 功能固定 | 🌱 **能成长** — 从经验中学习，能自己生成新技能 |
| 一个风格到底 | 👤 **有性格** — 保守派/运动派/老司机三种人格 |
| 你问它才答 | 👋 **会主动** — 像副驾一样主动提醒风险 |

---

## 30 秒上手

```bash
pip install -r requirements.txt
python -m Nonull
# 看到 >>> 就可以开始用了
```

```python
from core import Nonull
agent = Nonull()
result = agent.run_sync("分析这段代码")
print(result["output"])
```

---

## 核心功能速览

| 模块 | 功能 |
|------|------|
| 🤖 **核心大脑** | ReAct + 规划 + 反思 融合引擎 |
| 🧠 **记忆系统** | 工作/情景/知识/技能 四种记忆 |
| 🛡️ **安全卫士** | ISO 26262 + Deny-First + 五关检查 |
| 🔧 **27个技能** | 代码/安全/感知/规划/测试/仿真/数据/研究/DevOps |
| 🔄 **多Agent协作** | DAG任务分解，8个Agent并行 |
| 👤 **驾驶人格** | 保守派/运动派/老司机，三种性格 |
| 🏅 **安全徽章** | 像打游戏一样攒安全徽章 |
| 🌱 **自我进化** | 从经验中学习，自动生成新技能 |
| 🔌 **多通道** | CLI / API / 飞书 / 钉钉 / Telegram |

---

## 快速了解各模块

```
📂 智能体/
├── core/            核心大脑
├── memory/          记忆系统（不会忘）
├── safety/          安全卫士（不出事）
├── skills/          27个技能（啥都会）
├── persona/         👈 独有：人格+场景+徽章
├── orchestration/   多Agent协作
├── evolution/       自我进化（越来越强）
├── consciousness/   自我意识
├── docs/            详细说明书
└── examples/        使用示例
```

---

## 详细文档

- 📖 [完整说明书](docs/说明书-完整版.md) — 功能详解 + 使用指南
- 📄 [一页纸速览](docs/一页纸速览.md) — 一分钟看完
- 🚀 [快速上手指南](docs/快速上手指南.md) — 2 分钟上手
- 🏗️ [架构文档](docs/architecture.md) — 架构深度解析

---

## Nonull = 非空 = Never Null

每一个决策都有依据，每一次响应都有内容，每一个动作都经过安全验证。
