"""
Tests for new feature modules (Round 3):
- Action Registry (Browser-use pattern)
- Filter Pipeline (Semantic Kernel pattern)
- Eval Judge (Mastra/Langfuse pattern)
- Session Memory (Agno pattern)
- Prompt Registry (Langfuse pattern)
"""
import asyncio
import time
import pytest


# -- Action Registry ---------------------------------------------------------

class TestActionRegistry:
    def test_import(self):
        from core.action_registry import ActionRegistry, ActionInfo, ActionResult
        assert ActionRegistry is not None

    def test_decorator_registration(self):
        from core.action_registry import ActionRegistry
        reg = ActionRegistry()

        @reg.action("greet", "Say hello")
        def greet(name: str, loud: bool = False) -> str:
            return f"Hello {name}{'!' if loud else '.'}"

        assert "greet" in reg
        assert len(reg) == 1

    def test_execute(self):
        from core.action_registry import ActionRegistry
        reg = ActionRegistry()

        @reg.action("add", "Add numbers")
        def add(a: int, b: int) -> int:
            return a + b

        result = reg.execute("add", a=3, b=5)
        assert result.success
        assert result.data == 8
        assert result.duration_ms >= 0

    def test_execute_missing(self):
        from core.action_registry import ActionRegistry
        reg = ActionRegistry()
        result = reg.execute("nonexistent")
        assert not result.success
        assert result.error is not None

    def test_execute_error(self):
        from core.action_registry import ActionRegistry
        reg = ActionRegistry()

        @reg.action("fail", "Always fails")
        def fail():
            raise ValueError("boom")

        result = reg.execute("fail")
        assert not result.success
        assert "boom" in result.error

    def test_openai_tools_export(self):
        from core.action_registry import ActionRegistry
        reg = ActionRegistry()

        @reg.action("search", "Search for items")
        def search(query: str, limit: int = 10) -> list:
            return []

        tools = reg.to_openai_tools()
        assert len(tools) == 1
        tool = tools[0]
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "search"
        assert "query" in tool["function"]["parameters"]["properties"]

    def test_unregister(self):
        from core.action_registry import ActionRegistry
        reg = ActionRegistry()

        @reg.action("temp", "Temporary")
        def temp():
            pass

        assert "temp" in reg
        reg.unregister("temp")
        assert "temp" not in reg

    def test_list_actions_by_tag(self):
        from core.action_registry import ActionRegistry
        reg = ActionRegistry()

        @reg.action("a", "Action A", tags=["safety"])
        def a():
            pass

        @reg.action("b", "Action B", tags=["memory"])
        def b():
            pass

        safety_actions = reg.list_actions(tag="safety")
        assert len(safety_actions) == 1
        assert safety_actions[0].name == "a"

    def test_auto_schema_optional(self):
        from core.action_registry import ActionRegistry
        from typing import Optional
        reg = ActionRegistry()

        @reg.action("opt", "Optional param test")
        def opt(required: str, optional: Optional[int] = None):
            pass

        info = reg.get("opt")
        assert info is not None
        params = info.parameters
        assert "required" in params.get("required", [])

    def test_from_class(self):
        from core.action_registry import ActionRegistry
        reg = ActionRegistry()

        class MyTools:
            @reg.action("tool_a", "Tool A")
            def tool_a(self, x: int) -> int:
                return x * 2

        obj = MyTools()
        assert "tool_a" in reg


# -- Filter Pipeline ---------------------------------------------------------

class TestFilterPipeline:
    def test_import(self):
        from core.filter_pipeline import FilterPipeline, Filter, InvocationContext
        assert FilterPipeline is not None

    def test_logging_filter(self):
        from core.filter_pipeline import FilterPipeline, LoggingFilter
        pipeline = FilterPipeline()
        pipeline.add(LoggingFilter())
        result = pipeline.execute("test_op", {"data": "hello"}, lambda d: {"result": "ok"})
        assert result is not None

    def test_timing_filter(self):
        from core.filter_pipeline import FilterPipeline, TimingFilter
        pipeline = FilterPipeline()
        pipeline.add(TimingFilter())

        captured = {}
        def run_fn(data):
            time.sleep(0.01)
            return {"done": True}

        result = pipeline.execute("test_op", {"x": 1}, run_fn)
        assert result is not None

    def test_pipeline_chain(self):
        from core.filter_pipeline import FilterPipeline, LoggingFilter, TimingFilter, TokenCountFilter
        pipeline = FilterPipeline()
        pipeline.add(LoggingFilter(), priority=1)
        pipeline.add(TimingFilter(), priority=2)
        pipeline.add(TokenCountFilter(), priority=0)

        result = pipeline.execute("llm_call", {"prompt": "Hello world"}, lambda d: {"response": "Hi"})
        assert result is not None

    def test_cancel(self):
        from core.filter_pipeline import FilterPipeline, Filter, InvocationContext
        class BlockFilter(Filter):
            @property
            def name(self):
                return "blocker"
            def on_before(self, ctx):
                ctx.cancelled = True
                return ctx
            def on_after(self, ctx):
                return ctx
            def on_error(self, ctx, error):
                return ctx

        pipeline = FilterPipeline()
        pipeline.add(BlockFilter())
        result = pipeline.execute("op", {"x": 1}, lambda d: d)
        assert result is None or result == {}

    def test_remove_filter(self):
        from core.filter_pipeline import FilterPipeline, LoggingFilter
        pipeline = FilterPipeline()
        pipeline.add(LoggingFilter())
        assert len(pipeline.list_filters()) == 1
        pipeline.remove("logging")
        assert len(pipeline.list_filters()) == 0

    def test_error_handling(self):
        from core.filter_pipeline import FilterPipeline, LoggingFilter
        pipeline = FilterPipeline()
        pipeline.add(LoggingFilter())

        with pytest.raises(Exception):
            pipeline.execute("op", {}, lambda d: (_ for _ in ()).throw(RuntimeError("fail")))


# -- Eval Judge ---------------------------------------------------------------

class TestEvalJudge:
    def test_import(self):
        from core.eval_judge import EvalJudge, EvalMetric, EvalResult
        assert EvalJudge is not None

    def test_evaluate_single(self):
        from core.eval_judge import EvalJudge, EvalMetric

        def mock_llm(prompt):
            return "Score: 0.85\nReasoning: The output is relevant and accurate."

        judge = EvalJudge(llm_fn=mock_llm)
        result = judge.evaluate("The car should slow down.", context="Approaching red light")
        assert result.score == 0.85
        assert result.passed
        assert "relevant" in result.reasoning

    def test_evaluate_low_score(self):
        from core.eval_judge import EvalJudge, EvalMetric

        def mock_llm(prompt):
            return "Score: 0.3\nReasoning: The output is not relevant."

        judge = EvalJudge(llm_fn=mock_llm, threshold=0.7)
        result = judge.evaluate("Random text", context="Safety analysis")
        assert result.score == 0.3
        assert not result.passed

    def test_evaluate_all(self):
        from core.eval_judge import EvalJudge, EvalMetric

        def mock_llm(prompt):
            return "Score: 0.9\nReasoning: Good quality."

        judge = EvalJudge(llm_fn=mock_llm)
        report = judge.evaluate_all("Good output", context="Test context")
        assert report.passed
        assert report.overall_score >= 0.8
        assert len(report.results) > 0

    def test_batch_evaluate(self):
        from core.eval_judge import EvalJudge

        def mock_llm(prompt):
            return "Score: 0.8\nReasoning: Acceptable."

        judge = EvalJudge(llm_fn=mock_llm)
        items = [
            {"output": "Result A", "context": "Context A"},
            {"output": "Result B", "context": "Context B"},
        ]
        reports = judge.batch_evaluate(items)
        assert len(reports) == 2

    def test_custom_metric(self):
        from core.eval_judge import EvalJudge, EvalMetric

        def mock_llm(prompt):
            return "Score: 0.95\nReasoning: Meets safety standards."

        judge = EvalJudge(llm_fn=mock_llm)
        judge.add_custom_metric("safety_compliance", "Evaluate if {output} meets safety standards. Score 0-1.")
        result = judge.evaluate("Brake applied", metric=EvalMetric.CUSTOM)
        assert result.score == 0.95

    def test_parse_various_formats(self):
        from core.eval_judge import EvalJudge

        formats = [
            ("Score: 0.7\nReasoning: ok", 0.7),
            ("The score is 0.5 out of 1.0.\nBecause...", 0.5),
            ("0.9\nGood", 0.9),
        ]
        for text, expected in formats:
            judge = EvalJudge(llm_fn=lambda p, t=text: t)
            result = judge.evaluate("test")
            assert abs(result.score - expected) < 0.01, f"Failed for: {text}"

    def test_summary(self):
        from core.eval_judge import EvalJudge

        def mock_llm(prompt):
            return "Score: 0.8\nReasoning: Solid."

        judge = EvalJudge(llm_fn=mock_llm)
        report = judge.evaluate_all("output", context="ctx")
        summary = report.summary()
        assert isinstance(summary, str)
        assert len(summary) > 0


# -- Session Memory -----------------------------------------------------------

class TestSessionMemory:
    def test_import(self):
        from core.session_memory import SessionMemory, SessionMessage
        assert SessionMemory is not None

    def test_create_session(self):
        from core.session_memory import SessionMemory
        mem = SessionMemory()
        sid = mem.create_session()
        assert sid is not None
        assert sid in mem.list_sessions()

    def test_add_and_get_messages(self):
        from core.session_memory import SessionMemory, MessageRole
        mem = SessionMemory()
        sid = mem.create_session("test-session")
        mem.add_message(sid, MessageRole.USER, "Hello")
        mem.add_message(sid, MessageRole.ASSISTANT, "Hi there!")

        messages = mem.get_messages(sid)
        assert len(messages) == 2
        assert messages[0].content == "Hello"

    def test_get_context(self):
        from core.session_memory import SessionMemory, MessageRole
        mem = SessionMemory()
        sid = mem.create_session()
        mem.add_message(sid, MessageRole.USER, "What is ADAS?")
        mem.add_message(sid, MessageRole.ASSISTANT, "Advanced Driver Assistance Systems.")

        ctx = mem.get_context(sid)
        assert "ADAS" in ctx

    def test_auto_summarize(self):
        from core.session_memory import SessionMemory, MessageRole
        mem = SessionMemory(max_tokens=100)
        sid = mem.create_session()

        for i in range(50):
            mem.add_message(sid, MessageRole.USER, f"Message number {i} with some extra content to fill tokens.")

        record = mem._sessions[sid]
        assert record.summary != "" or len(record.messages) < 50

    def test_extract_facts(self):
        from core.session_memory import SessionMemory, MessageRole
        mem = SessionMemory()
        sid = mem.create_session()
        mem.add_message(sid, MessageRole.USER, "The speed limit is 60 km/h.")
        mem.add_message(sid, MessageRole.ASSISTANT, "LiDAR has a range of 200 meters.")

        mem.extract_facts(sid)
        facts = mem.get_facts(sid)
        assert len(facts) > 0

    def test_clear_session(self):
        from core.session_memory import SessionMemory, MessageRole
        mem = SessionMemory()
        sid = mem.create_session()
        mem.add_message(sid, MessageRole.USER, "Test")
        mem.clear_session(sid)
        assert sid not in mem.list_sessions()

    def test_export_import(self):
        from core.session_memory import SessionMemory, MessageRole
        mem = SessionMemory()
        sid = mem.create_session("export-test")
        mem.add_message(sid, MessageRole.USER, "Hello")

        data = mem.export_session(sid)
        assert data["session_id"] == "export-test"

        mem2 = SessionMemory()
        imported_sid = mem2.import_session(data)
        assert imported_sid == "export-test"
        assert len(mem2.get_messages(imported_sid)) == 1

    def test_stats(self):
        from core.session_memory import SessionMemory, MessageRole
        mem = SessionMemory()
        sid = mem.create_session()
        mem.add_message(sid, MessageRole.USER, "Test message")
        stats = mem.stats()
        assert stats["session_count"] >= 1


# -- Prompt Registry ----------------------------------------------------------

class TestPromptRegistry:
    def test_import(self):
        from core.prompt_registry import PromptRegistry, PromptVersion, CompiledPrompt
        assert PromptRegistry is not None

    def test_register_and_get(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        v = reg.register("greeting", "Hello {{name}}, welcome to {{place}}!")
        assert v.version == 1
        assert "name" in v.variables
        assert "place" in v.variables

    def test_compile(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        reg.register("greet", "Hello {{name}}!")
        compiled = reg.compile("greet", name="Alice")
        assert compiled.text == "Hello Alice!"
        assert compiled.variables_used["name"] == "Alice"

    def test_versioning(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        v1 = reg.register("task", "Do {{action}} v1")
        v2 = reg.register("task", "Do {{action}} v2")
        assert v1.version == 1
        assert v2.version == 2

        latest = reg.get("task")
        assert latest.version == 2

        old = reg.get("task", version=1)
        assert "v1" in old.template

    def test_labels(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        reg.register("analyze", "Analyze {{topic}} for safety", labels=["staging"])
        reg.register("analyze", "Analyze {{topic}} for safety (improved)")
        reg.promote("analyze", 1, "production")

        prod = reg.get("analyze", label="production")
        assert prod.version == 1

        latest = reg.get("analyze")
        assert latest.version == 2

    def test_promote_demote(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        reg.register("plan", "Plan {{task}}")
        reg.promote("plan", 1, "production")

        v = reg.get("plan", label="production")
        assert v is not None

        reg.demote("plan", 1, "production")
        v = reg.get("plan", label="production")
        assert v is None

    def test_default_values(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        reg.register("msg", "Hello {{name|World}}!")
        compiled = reg.compile("msg")
        assert compiled.text == "Hello World!"

        compiled2 = reg.compile("msg", name="Alice")
        assert compiled2.text == "Hello Alice!"

    def test_missing_variable_error(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        reg.register("strict", "Do {{action}} now")
        with pytest.raises(ValueError):
            reg.compile("strict")

    def test_delete(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        reg.register("temp", "Temp prompt")
        reg.delete("temp")
        assert reg.get("temp") is None

    def test_export_import(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        reg.register("a", "Template A {{x}}", tags=["test"])
        reg.register("b", "Template B")

        json_str = reg.export_json()
        restored = PromptRegistry.from_json(json_str)
        assert len(restored.list_prompts()) == 2

    def test_list_by_tag(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        reg.register("safety", "Check {{item}}", tags=["safety"])
        reg.register("general", "Do {{thing}}", tags=["general"])

        safety_prompts = reg.list_prompts(tag="safety")
        assert len(safety_prompts) == 1

    def test_history(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        reg.register("evolve", "Version 1")
        reg.register("evolve", "Version 2")
        reg.register("evolve", "Version 3")

        history = reg.get_history("evolve")
        assert len(history) == 3

    def test_stats(self):
        from core.prompt_registry import PromptRegistry
        reg = PromptRegistry()
        reg.register("a", "Prompt A")
        reg.register("b", "Prompt B")
        stats = reg.stats()
        assert stats["total_prompts"] == 2
        assert stats["total_versions"] == 2
