# Nonull Skills Catalog 技能目录

> **完整技能目录 — 覆盖智驾开发全生命周期的 AI 技能**
> **Complete Skills Catalog — AI Skills Covering the Full ADAS Development Lifecycle**

---

## / 目录 / Table of Contents

1. [概述 / Overview](#1-概述--overview)
2. [代码审查 / Code Review](#2-代码审查--code-review)
3. [安全分析 / Safety Analysis](#3-安全分析--safety-analysis)
4. [架构设计 / Architecture Design](#4-架构设计--architecture-design)
5. [需求分析 / Requirement Analysis](#5-需求分析--requirement-analysis)
6. [测试生成 / Test Generation](#6-测试生成--test-generation)
7. [性能分析 / Performance Analysis](#7-性能分析--performance-analysis)
8. [回归检查 / Regression Check](#8-回归检查--regression-check)
9. [文档生成 / Document Generation](#9-文档生成--document-generation)
10. [技能开发 / Skill Development](#10-技能开发--skill-development)

---

## 1. 概述 / Overview

Nonull 内置了 31 个技能（见 `skills/__init__.py` 的 `__all__`），覆盖智驾系统开发的完整生命周期。本目录列出 8 个代表性核心技能（按功能域挑选）。每个技能都经过安全级别评估，与系统的拒绝优先安全策略集成。

Nonull ships with 31 skills (see `__all__` in `skills/__init__.py`) covering the full lifecycle of autonomous driving system development. This catalog highlights 8 representative core skills (selected by functional domain). Each skill is safety-level assessed and integrated with the system's deny-first safety policy.

### Skill Overview Table

| # | Skill | Category | Safety Level | Auto-Discover | Version |
|---|---|---|---|---|---|
| 1 | `code-review` | CODE | 2 | Yes | 1.0.0 |
| 2 | `safety-analysis` | SAFETY | 4 | Yes | 1.0.0 |
| 3 | `architecture-design` | ARCHITECTURE | 2 | Yes | 1.0.0 |
| 4 | `requirement-analysis` | REQUIREMENT | 3 | Yes | 1.0.0 |
| 5 | `test-generation` | TEST | 2 | Yes | 1.0.0 |
| 6 | `perf-analysis` | PERFORMANCE | 1 | Yes | 1.0.0 |
| 7 | `regression-check` | CODE | 2 | Yes | 1.0.0 |
| 8 | `document-generation` | DOCUMENT | 1 | Yes | 1.0.0 |

### Skill Naming Convention

```
Skill names follow the kebab-case convention:
- code-review        (代码审查)
- safety-analysis    (安全分析)
- architecture-design (架构设计)
- requirement-analysis (需求分析)
- test-generation    (测试生成)
- perf-analysis      (性能分析)
- regression-check   (回归检查)
- document-generation (文档生成)
```

### Skill Versioning

All skills follow Semantic Versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Incompatible API changes or safety level changes
- **MINOR**: New functionality in a backward-compatible manner
- **PATCH**: Backward-compatible bug fixes

---

## 2. 代码审查 / Code Review

### 概述 / Overview

```
Skill: code-review
Category: CODE
Safety Level: 2 (LOW)
Version: 1.0.0
Dependencies: []
```

自动审查 ADAS 相关的 C/C++ 和 Python 代码，检查编码规范、安全相关模式和潜在缺陷。

Automatically reviews ADAS-related C/C++ and Python code, checking coding standards, safety-related patterns, and potential defects.

### 触发条件 / Trigger Conditions

| Condition | Example |
|---|---|
| User explicitly requests code review | "Review this C++ code" |
| User pastes code in chat | (code block detected) |
| User references a file path | "Review src/braking/controller.cpp" |
| Commit message suggests changes | "Fix potential overflow in speed calculation" |
| CI/CD pipeline integration | Post-commit hook |

### 检查项 / Checks Performed

```
Code Review Checks:
├── MISRA C++ Compliance (MISRA C++ 2023)
│   ├── Rule 0-1-1: No unreachable code
│   ├── Rule 5-0-1: No implicit conversions
│   ├── Rule 7-5-1: No dynamic memory allocation after init
│   └── Rule 15-5-1: All switch cases covered
│
├── AUTOSAR C++14 Guidelines
│   ├── A1-1-1: No use of long long
│   ├── A2-3-1: No undefined behavior
│   └── A7-1-1: constexpr where possible
│
├── Safety Patterns
│   ├── Range checking on all sensor inputs
│   ├── Redundancy in critical paths
│   ├── No unprotected shared state
│   ├── Proper error propagation
│   └── Timeout handling in all loops
│
├── Performance Patterns
│   ├── No heap allocation in real-time paths
│   ├── Cache-friendly data access patterns
│   ├── Proper use of move semantics
│   └── No unnecessary copies
│
└── Best Practices
    ├── Meaningful naming conventions
    ├── Appropriate comment density
    ├── Single responsibility principle
    ├── Proper exception handling
    └── Complete unit test coverage
```

### 输入参数 / Input Parameters

```yaml
code-review:
  params:
    code:
      type: string
      description: "代码内容 / Source code content"
      required: true
    language:
      type: string
      description: "编程语言 / Programming language (cpp, python, c)"
      required: false
      default: auto-detect
    file_path:
      type: string
      description: "文件路径（用于上下文） / File path for context"
      required: false
    strictness:
      type: integer
      description: "审查严格度 / Review strictness (1-5)"
      required: false
      default: 3
    focus:
      type: string
      description: "审查重点 / Review focus (safety, performance, style, all)"
      required: false
      default: "all"
```

### 输出格式 / Output Format

```yaml
code-review-result:
  summary:
    total_issues: integer
    critical: integer
    major: integer
    minor: integer
    info: integer
  issues:
    - id: string
      severity: "critical" | "major" | "minor" | "info"
      rule: string
      file: string
      line: integer
      message: string
      recommendation: string
      category: "safety" | "performance" | "style" | "best-practice"
  score:
    overall: float  # 0-100
    safety: float
    performance: float
    style: float
    coverage: float
```

### 示例 / Example

**Input:**
```cpp
// AEB controller implementation
void AEBController::process(const SensorData& data) {
    if (data.velocity > 0) {
        // Calculate braking force
        float force = data.velocity * data.mass;
        applyBrake(force);
    }
}
```

**Output:**
```yaml
summary:
  total_issues: 4
  critical: 1
  major: 1
  minor: 2
issues:
  - id: CRIT-001
    severity: critical
    rule: "MISRA 5-0-1"
    message: "Implicit conversion from double to float may lose precision"
    line: 4
    recommendation: "Use double for all safety-critical calculations"
  - id: MAJ-001
    severity: major
    rule: "SAFETY-RANGE-001"
    message: "Missing input range validation for data.velocity"
    line: 3
    recommendation: "Add bounds check: if (velocity < 0 || velocity > MAX_SPEED)"
  - id: MIN-001
    severity: minor
    rule: "BEST-NAMED-001"
    message: "Function name 'process' is too generic"
    line: 2
    recommendation: "Rename to 'evaluateBrakingForce'"
score:
  overall: 72
  safety: 65
  performance: 85
  style: 70
```

---

## 3. 安全分析 / Safety Analysis

### 概述 / Overview

```
Skill: safety-analysis
Category: SAFETY
Safety Level: 4 (HIGH)
Version: 1.0.0
Dependencies: []
```

执行功能安全分析，包括 HARA（危险分析和风险评估）、FMEA（失效模式与影响分析）和 FTA（故障树分析）。

Performs functional safety analysis including HARA (Hazard Analysis and Risk Assessment), FMEA (Failure Mode and Effects Analysis), and FTA (Fault Tree Analysis).

### 触发条件 / Trigger Conditions

| Condition | Example |
|---|---|
| User requests safety analysis | "Perform HARA on the AEB function" |
| New function introduced | "Analyze safety requirements for lane keep assist" |
| Design change | "Impact analysis of changing the braking algorithm" |
| Safety review milestone | "Pre-release safety audit" |
| Incident investigation | "Root cause analysis of unintended acceleration report" |

### 分析方法 / Analysis Methods

```
Safety Analysis Methods:
┌─────────────────────────────────────────────────────────────┐
│                         HARA                                 │
│  Hazard Analysis and Risk Assessment (ISO 26262-3)          │
├─────────────────────────────────────────────────────────────┤
│  1. Item Definition                                         │
│  2. Hazard Identification (operational situations +       │
│     malfunctions)                                           │
│  3. Hazard Classification (S, E, C → ASIL A-D)             │
│  4. Safety Goals Definition                                 │
│  5. Verification of Coverage                                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                         FMEA                                 │
│  Failure Mode and Effects Analysis (AIAG/VDA)               │
├─────────────────────────────────────────────────────────────┤
│  1. System Analysis                                         │
│  2. Function Analysis                                       │
│  3. Failure Analysis (Failure Mode, Cause, Effect)          │
│  4. Risk Analysis (Severity, Occurrence, Detection → RPN)   │
│  5. Optimization (Recommended Actions)                      │
│  6. Result Documentation                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                         FTA                                  │
│  Fault Tree Analysis                                        │
├─────────────────────────────────────────────────────────────┤
│  1. Top Event Definition                                    │
│  2. Fault Tree Construction (AND/OR gates)                  │
│  3. Minimal Cut Set Analysis                                │
│  4. Quantitative Analysis (Probability)                     │
│  5. Sensitivity Analysis                                    │
└─────────────────────────────────────────────────────────────┘
```

### 输入参数 / Input Parameters

```yaml
safety-analysis:
  params:
    function_name:
      type: string
      description: "被分析的功能名称 / Name of the function to analyze"
      required: true
    analysis_type:
      type: string
      description: "分析类型 / Analysis type (hara, fmea, fta, all)"
      required: false
      default: "hara"
    system_description:
      type: string
      description: "系统描述 / System description"
      required: true
    context:
      type: string
      description: "运行上下文 / Operational context"
      required: false
    existing_hazards:
      type: array
      description: "已知危险列表 / List of known hazards"
      required: false
```

### 输出格式 / Output Format — HARA

```yaml
safety-analysis-result:
  analysis_type: "hara"
  item_definition:
    name: string
    description: string
    boundaries: string[]
    interfaces: string[]
  hazards:
    - id: string
      hazard: string
      situation: string
      severity: "S0" | "S1" | "S2" | "S3"
      exposure: "E0" | "E1" | "E2" | "E3" | "E4"
      controllability: "C0" | "C1" | "C2" | "C3"
      asil: "QM" | "ASIL_A" | "ASIL_B" | "ASIL_C" | "ASIL_D"
      safety_goal:
        id: string
        description: string
        asil: string
  summary:
    total_hazards: integer
    asil_d: integer
    asil_c: integer
    asil_b: integer
    asil_a: integer
    qm: integer
```

### 示例 / Example

**Input:**
```
Analyze the AEB (Autonomous Emergency Braking) function using HARA.
System: AEB automatically applies brakes when collision is imminent.
Context: Highway driving, speeds 60-120 km/h.
```

**Output:**
```yaml
item_definition:
  name: "Autonomous Emergency Braking (AEB)"
  description: "System that detects potential collisions and automatically applies brakes"
  boundaries:
    - "Sensor input (radar + camera fusion)"
    - "Brake actuator output"
    - "Driver override (steering wheel torque, accelerator pedal)"
  interfaces:
    - "CAN bus to ESC"
    - "Ethernet to perception stack"
    - "Driver HMI (visual + audible warnings)"
hazards:
  - id: "H-001"
    hazard: "Unintended braking at highway speed"
    situation: "Vehicle traveling at 110 km/h, no obstacle ahead"
    severity: "S3"    # Life-threatening injuries
    exposure: "E3"    # Occurs >10% of driving time
    controllability: "C3"  # Difficult to control
    asil: "ASIL_D"
    safety_goal:
      id: "SG-001"
      description: "AEB shall not apply brakes exceeding 0.2g when no collision is predicted"
      asil: "ASIL_D"
  - id: "H-002"
    hazard: "Failure to brake when collision imminent"
    situation: "Vehicle approaching stationary vehicle at 80 km/h"
    severity: "S3"
    exposure: "E2"
    controllability: "C3"
    asil: "ASIL_C"
    safety_goal:
      id: "SG-002"
      description: "AEB shall detect obstacles >50m ahead and initiate braking >1.5s before collision"
      asil: "ASIL_C"
summary:
  total_hazards: 12
  asil_d: 3
  asil_c: 5
  asil_b: 3
  asil_a: 1
  qm: 0
```

---

## 4. 架构设计 / Architecture Design

### 概述 / Overview

```
Skill: architecture-design
Category: ARCHITECTURE
Safety Level: 2 (LOW)
Version: 1.0.0
Dependencies: []
```

评估和设计智驾系统架构，检查架构模式、组件交互、数据流和标准化符合性。

Evaluates and designs autonomous driving system architecture, checking architecture patterns, component interactions, data flows, and standards compliance.

### 触发条件 / Trigger Conditions

| Condition | Example |
|---|---|
| Architecture design request | "Design the software architecture for the perception stack" |
| Architecture review | "Review the current architecture for scalability" |
| Trade-off analysis | "Compare centralized vs. distributed architecture for ADAS" |
| Migration planning | "Plan migration from AUTOSAR Classic to Adaptive" |

### 检查项 / Checks Performed

```
Architecture Design Checks:
├── Architectural Patterns
│   ├── Layered architecture evaluation
│   ├── Microservices vs. monolithic analysis
│   ├── Event-driven architecture suitability
│   └── Component cohesion and coupling metrics
│
├── AUTOSAR Compliance
│   ├── AUTOSAR Classic Platform (R20-11)
│   ├── AUTOSAR Adaptive Platform (R21-11)
│   ├── BSW (Basic Software) layer mapping
│   ├── RTE (Runtime Environment) design
│   └── SWC (Software Component) decomposition
│
├── Safety Architecture (ISO 26262-6)
│   ├── ASIL decomposition feasibility
│   ├── Freedom-from-interference analysis
│   ├── Safety element out of context (SEooC)
│   └── Fault-tolerant time interval (FTTI) analysis
│
├── Data Flow Design
│   ├── Sensor data pipeline latency
│   ├── Fusion architecture (early vs. late fusion)
│   ├── End-to-end data protection
│   └── Bandwidth and throughput analysis
│
└── Scalability & Extensibility
    ├── Hardware abstraction layer design
    ├── Feature integration roadmap
    ├── OTA update capability
    └── Multi-ECU/SOC deployment strategy
```

---

## 5. 需求分析 / Requirement Analysis

### 概述 / Overview

```
Skill: requirement-analysis
Category: REQUIREMENT
Safety Level: 3 (MEDIUM)
Version: 1.0.0
Dependencies: []
```

分析和管理智驾系统需求，包括需求提取、追溯性分析、一致性检查和安全需求分配。

Analyzes and manages ADAS system requirements, including requirement extraction, traceability analysis, consistency checking, and safety requirement allocation.

### 检查项 / Checks Performed

```
Requirement Analysis Checks:
├── Requirement Quality
│   ├── SMART criteria validation
│   ├── Unambiguous language check
│   ├── Atomic requirement verification
│   └── Feasibility assessment
│
├── Traceability Analysis
│   ├── Customer ↔ System requirements trace
│   ├── System ↔ Software requirements trace
│   ├── Requirements ↔ Test cases trace
│   ├── Requirements ↔ Safety goals trace
│   └── Gap analysis (untraced requirements)
│
├── Consistency Check
│   ├── No conflicting requirements
│   ├── No duplicate requirements
│   ├── Hierarchical consistency
│   └── Cross-reference integrity
│
└── Safety Requirement Allocation
    ├── ASIL allocation per requirement
    ├── Safety mechanism identification
    ├── Fault detection coverage
    └── Safety validation criteria
```

---

## 6. 测试生成 / Test Generation

### 概述 / Overview

```
Skill: test-generation
Category: TEST
Safety Level: 2 (LOW)
Version: 1.0.0
Dependencies: []
```

自动生成测试用例，包括单元测试、集成测试、MIL/SIL/HIL 测试场景和回归测试套件。

Automatically generates test cases including unit tests, integration tests, MIL/SIL/HIL test scenarios, and regression test suites.

### 测试类型 / Test Types

```
Test Generation Types:
┌─────────────────────────────────────────────────────────────┐
│                    TEST GENERATION                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Unit Tests (单元测试)                                       │
│  ├── C++: Google Test (gtest)                                │
│  ├── Python: pytest                                         │
│  └── Coverage-guided generation                              │
│                                                              │
│  Integration Tests (集成测试)                                 │
│  ├── Component interaction tests                            │
│  ├── Interface compliance tests                             │
│  └── End-to-end data flow tests                             │
│                                                              │
│  Safety Tests (安全测试)                                     │
│  ├── Fault injection tests                                  │
│  ├── Error handling tests                                   │
│  └── Timing constraint tests                                │
│                                                              │
│  Scenario Tests (场景测试)                                   │
│  ├── Euro NCAP test scenarios                               │
│  ├── ISO 26262 validation scenarios                         │
│  └── Edge case scenarios                                    │
│                                                              │
│  Regression Tests (回归测试)                                 │
│  ├── Impact analysis-based selection                        │
│  ├── Historical failure replay                              │
│  └── Performance regression detection                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 性能分析 / Performance Analysis

### 概述 / Overview

```
Skill: perf-analysis
Category: PERFORMANCE
Safety Level: 1 (MINIMAL)
Version: 1.0.0
Dependencies: []
```

分析智驾系统性能，包括实时性分析、资源利用率、延迟瓶颈和优化建议。

Analyzes ADAS system performance including real-time analysis, resource utilization, latency bottlenecks, and optimization recommendations.

### 分析维度 / Analysis Dimensions

```
Performance Analysis:
├── Timing Analysis
│   ├── Worst-case execution time (WCET)
│   ├── Frame processing latency
│   ├── Sensor-to-actuator latency
│   ├── Inter-core/inter-processor communication delay
│   └── Task scheduling jitter
│
├── Resource Utilization
│   ├── CPU load per core
│   ├── GPU / NPU utilization
│   ├── Memory usage (stack, heap, DMA)
│   ├── Bus bandwidth (CAN, Ethernet, PCIe)
│   └── Storage I/O
│
├── Scalability Analysis
│   ├── Bottleneck identification
│   ├── Amdahl's law analysis
│   ├── Horizontal scaling feasibility
│   └── Algorithmic complexity (big O)
│
└── Optimization Recommendations
    ├── Algorithm selection changes
    ├── Data structure optimizations
    ├── Parallelization opportunities
    ├── Memory access pattern improvements
    └── Cache optimization strategies
```

---

## 8. 回归检查 / Regression Check

### 概述 / Overview

```
Skill: regression-check
Category: CODE
Safety Level: 2 (LOW)
Version: 1.0.0
Dependencies: []
```

分析代码变更的影响，识别可能受影响的模块、测试用例和安全相关功能。

Analyzes the impact of code changes, identifying potentially affected modules, test cases, and safety-related functionality.

### 分析范围 / Analysis Scope

```
Regression Check Scope:
├── Code Impact Analysis
│   ├── Changed function callers
│   ├── Changed class hierarchy
│   ├── Changed interfaces
│   └── Data dependency chain
│
├── Test Impact Analysis
│   ├── Directly affected test cases
│   ├── Indirectly affected test suites
│   ├── Required new test cases
│   └── Deprecated test cases
│
├── Safety Impact Analysis
│   ├── Affected safety goals
│   ├── Affected safety mechanisms
│   ├── ASIL decomposition changes
│   └── New hazard introduction
│
└── Documentation Impact
    ├── Architecture documentation updates needed
    ├── Requirement specification updates
    └── Safety case updates
```

---

## 9. 文档生成 / Document Generation

### 概述 / Overview

```
Skill: document-generation
Category: DOCUMENT
Safety Level: 1 (MINIMAL)
Version: 1.0.0
Dependencies: []
```

根据分析结果自动生成文档，包括安全案例、架构文档、测试报告和需求规格。

Automatically generates documentation based on analysis results, including safety cases, architecture documents, test reports, and requirement specifications.

### 文档类型 / Document Types

```yaml
document-generation:
  document_types:
    safety_case:
      description: "ISO 26262 安全案例 / ISO 26262 Safety Case"
      template: "safety_case_template.md"
      sections:
        - "Item definition"
        - "HARA results"
        - "Safety goals"
        - "Functional safety concept"
        - "Technical safety concept"
        - "Safety validation"
        - "Safety case conclusion"

    architecture_document:
      description: "系统架构文档 / System Architecture Document"
      template: "architecture_template.md"
      sections:
        - "System overview"
        - "Architecture diagram"
        - "Component specifications"
        - "Interface definitions"
        - "Data flow diagrams"
        - "Deployment view"

    test_report:
      description: "测试报告 / Test Report"
      template: "test_report_template.md"
      sections:
        - "Test summary"
        - "Test coverage"
        - "Pass/fail statistics"
        - "Defect analysis"
        - "Risk assessment"

    requirement_spec:
      description: "需求规格 / Requirement Specification"
      template: "requirement_template.md"
      sections:
        - "Functional requirements"
        - "Non-functional requirements"
        - "Safety requirements"
        - "Traceability matrix"
        - "Glossary"
```

---

## 10. 技能开发 / Skill Development

### 创建自定义技能 / Creating Custom Skills

To create a custom skill for Nonull:

```python
# skills/my_custom_skill.py
from Nonull.skill_base import (
    BaseSkill, SkillManifest, SkillContext, SkillResult,
    SafetyLevel, SkillCategory
)

class MyCustomSkill(BaseSkill):
    """自定义技能描述 / Custom skill description (中英双语)."""

    manifest = SkillManifest(
        name="my-custom-skill",
        version="1.0.0",
        description="执行自定义分析任务 / Performs custom analysis tasks",
        category=SkillCategory.GENERAL,
        safety_level=SafetyLevel.LOW,
        requires=["numpy>=1.24"]
    )

    async def execute(
        self, context: SkillContext, **params
    ) -> SkillResult:
        # Skill logic here
        result = await self._perform_analysis(params)
        return SkillResult(
            success=True,
            data=result,
            summary="Analysis complete / 分析完成"
        )
```

### 技能注册 / Skill Registration

```bash
# 从本地文件注册 / Register from local file
python -m nonull skill register ./skills/my_custom_skill.py

# 从目录自动发现 / Auto-discover from directory
python -m nonull skill discover ./skills/

# 从技能市场安装 / Install from marketplace
python -m nonull skill install my-custom-skill

# 列出所有技能 / List all skills
python -m nonull skill list

# 移除技能 / Remove a skill
python -m nonull skill remove my-custom-skill
```

### 技能开发指南 / Skill Development Guidelines

1. **安全级别匹配** — 技能的 `safety_level` 不得超过 Agent 当前的 `strictness` 配置
2. **双向描述** — `description` 必须包含中文和英文
3. **依赖声明** — 所有 Python 依赖必须在 `requires` 中声明
4. **类型注解** — 所有公共方法必须有完整的类型注解
5. **异步执行** — 技能必须支持异步执行 (`async def execute`)
6. **结果结构化** — 返回值必须为 `SkillResult` 类型
7. **错误处理** — 所有异常必须被捕获并转化为 `SkillResult(success=False, error=...)`
8. **审计兼容** — 技能执行的关键步骤必须调用 `context.log()` 记录

---

> **Skills are the building blocks. Catalog is the map.**
> **技能是积木。目录是地图。**
