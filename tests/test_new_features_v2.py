"""
Tests for new feature modules (Round 2):
- Guard Pipeline (Guardrails AI pattern)
- Structured Output with Retry (Instructor pattern)
- Prompt Optimizer (DSPy-lite)
- Knowledge Graph Memory (Mem0 pattern)
"""
import json
import pytest


# ── Guardrail Pipeline ──────────────────────────────────────────

class TestGuardrails:
    def test_import(self):
        from core.guardrails import Guard, Validator, OnFail, JsonValidator
        assert Guard is not None

    def test_json_validator_pass(self):
        from core.guardrails import JsonValidator
        v = JsonValidator()
        result = v.validate('{"key": "value"}')
        assert result.passed

    def test_json_validator_fail(self):
        from core.guardrails import JsonValidator
        v = JsonValidator()
        result = v.validate("not json at all")
        assert not result.passed

    def test_length_validator(self):
        from core.guardrails import LengthValidator, OnFail
        v = LengthValidator(min_length=5, max_length=10, on_fail=OnFail.FIX)
        assert v.validate("hello").passed
        assert not v.validate("hi").passed
        result = v.validate("this is way too long for the limit")
        assert not result.passed
        assert result.fix_value is not None
        assert len(result.fix_value) == 10

    def test_prohibited_pattern(self):
        from core.guardrails import ProhibitedPatternValidator
        v = ProhibitedPatternValidator(["password", "secret"])
        assert v.validate("normal text").passed
        assert not v.validate("my password is 123").passed

    def test_numeric_range(self):
        from core.guardrails import NumericRangeValidator
        v = NumericRangeValidator(min_val=0.0, max_val=1.0)
        assert v.validate(0.5).passed
        result = v.validate(1.5)
        assert not result.passed
        assert result.fix_value == 1.0

    def test_schema_validator(self):
        from core.guardrails import SchemaValidator
        v = SchemaValidator(required_keys={"action": str, "confidence": float})
        assert v.validate({"action": "go", "confidence": 0.9}).passed
        assert not v.validate({"action": "go"}).passed
        assert not v.validate("not a dict").passed

    def test_lambda_validator(self):
        from core.guardrails import LambdaValidator
        v = LambdaValidator(lambda x: isinstance(x, dict) and "id" in x)
        assert v.validate({"id": 1}).passed
        assert not v.validate({"no_id": 1}).passed

    def test_guard_pipeline_pass(self):
        from core.guardrails import Guard, JsonValidator, LengthValidator
        guard = Guard("test").use(
            JsonValidator(),
            LengthValidator(max_length=1000),
        )
        report = guard.validate('{"ok": true}')
        assert report.passed

    def test_guard_pipeline_block(self):
        from core.guardrails import Guard, JsonValidator, OnFail
        guard = Guard("test").use(JsonValidator(on_fail=OnFail.BLOCK))
        report = guard.validate("not json")
        assert not report.passed

    def test_guard_pipeline_fix(self):
        from core.guardrails import Guard, LengthValidator, OnFail
        guard = Guard("test").use(LengthValidator(max_length=5, on_fail=OnFail.FIX))
        report = guard.validate("too long text here")
        assert report.passed
        assert len(report.value) == 5

    def test_guard_pipeline_reask(self):
        from core.guardrails import Guard, JsonValidator, OnFail
        guard = Guard("test").use(JsonValidator(on_fail=OnFail.REASK))
        report = guard.validate("bad json")
        assert not report.passed
        assert len(report.reask_messages) > 0


# ── Structured Output ───────────────────────────────────────────

class TestStructuredOutput:
    def test_import(self):
        from core.structured_output import structured_call, ResponseSchema, extract_json
        assert structured_call is not None

    def test_extract_json_direct(self):
        from core.structured_output import extract_json
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_extract_json_from_markdown(self):
        from core.structured_output import extract_json
        text = 'Here is the result:\n```json\n{"action": "stop"}\n```\nDone.'
        result = extract_json(text)
        assert result == {"action": "stop"}

    def test_extract_json_embedded(self):
        from core.structured_output import extract_json
        text = 'The answer is {"x": 1} in JSON.'
        result = extract_json(text)
        assert result == {"x": 1}

    def test_extract_json_none(self):
        from core.structured_output import extract_json
        assert extract_json("no json here") is None

    def test_response_schema_validate_pass(self):
        from core.structured_output import ResponseSchema
        schema = ResponseSchema(required_keys={"action": str, "value": (int, float)})
        assert schema.validate({"action": "go", "value": 1.0}) is None

    def test_response_schema_validate_missing_key(self):
        from core.structured_output import ResponseSchema
        schema = ResponseSchema(required_keys={"action": str})
        error = schema.validate({"not_action": "x"})
        assert error is not None
        assert "Missing" in error

    def test_response_schema_validate_wrong_type(self):
        from core.structured_output import ResponseSchema
        schema = ResponseSchema(required_keys={"count": int})
        error = schema.validate({"count": "not_int"})
        assert error is not None
        assert "wrong type" in error

    def test_response_schema_custom_validator(self):
        from core.structured_output import ResponseSchema
        schema = ResponseSchema(
            required_keys={"score": (int, float)},
            validators=[lambda v: 0 <= v["score"] <= 1],
        )
        assert schema.validate({"score": 0.5}) is None
        assert schema.validate({"score": 2.0}) is not None

    def test_prompt_hint(self):
        from core.structured_output import ResponseSchema
        schema = ResponseSchema(
            required_keys={"action": str},
            optional_keys={"note": str},
        )
        hint = schema.to_prompt_hint()
        assert "action" in hint
        assert "required" in hint

    def test_structured_call_success(self):
        from core.structured_output import structured_call, ResponseSchema
        schema = ResponseSchema(required_keys={"result": str})
        def mock_llm(prompt):
            return '{"result": "hello"}'
        result = structured_call(mock_llm, "test", schema)
        assert result.value == {"result": "hello"}
        assert result.attempts == 1

    def test_structured_call_retry(self):
        from core.structured_output import structured_call, ResponseSchema
        schema = ResponseSchema(required_keys={"action": str})
        call_count = [0]
        def mock_llm(prompt):
            call_count[0] += 1
            if call_count[0] == 1:
                return "not json"
            return '{"action": "go"}'
        result = structured_call(mock_llm, "test", schema, max_retries=3)
        assert result.value == {"action": "go"}
        assert result.attempts == 2

    def test_structured_call_exhausted(self):
        from core.structured_output import structured_call, ResponseSchema, RetryExhausted
        schema = ResponseSchema(required_keys={"x": int})
        def mock_llm(prompt):
            return "always bad"
        with pytest.raises(RetryExhausted):
            structured_call(mock_llm, "test", schema, max_retries=2)


# ── Prompt Optimizer ─────────────────────────────────────────────

class TestPromptOptimizer:
    def test_import(self):
        from core.prompt_optimizer import PromptOptimizer, Signature, TraceCollector
        assert PromptOptimizer is not None

    def test_signature_build_prompt(self):
        from core.prompt_optimizer import Signature
        sig = Signature(
            name="test",
            instruction="Analyze the input",
            input_fields=["query"],
            output_fields=["answer"],
        )
        prompt = sig.build_prompt({"query": "hello"})
        assert "Analyze the input" in prompt
        assert "hello" in prompt

    def test_trace_collector(self):
        from core.prompt_optimizer import TraceCollector
        collector = TraceCollector()
        collector.record({"q": "a"}, "output1", score=0.9)
        collector.record({"q": "b"}, "output2", score=0.3)
        assert len(collector) == 2
        assert len(collector.get_passing()) == 1
        assert len(collector.get_failing()) == 1

    def test_trace_collector_stats(self):
        from core.prompt_optimizer import TraceCollector
        collector = TraceCollector()
        collector.record({}, "a", score=1.0)
        collector.record({}, "b", score=0.0)
        stats = collector.stats()
        assert stats["total"] == 2
        assert stats["avg_score"] == 0.5

    def test_demo_selector_top_k(self):
        from core.prompt_optimizer import TraceCollector, DemoSelector
        collector = TraceCollector()
        for i in range(10):
            collector.record({"i": str(i)}, f"out_{i}", score=i / 10.0)
        examples = DemoSelector.top_k(collector.get_passing(), k=3)
        assert len(examples) == 3
        assert examples[0].score >= examples[1].score

    def test_demo_selector_diverse(self):
        from core.prompt_optimizer import TraceCollector, DemoSelector
        collector = TraceCollector()
        collector.record({"type": "a"}, "out1", score=0.9)
        collector.record({"type": "a"}, "out2", score=0.8)
        collector.record({"type": "b"}, "out3", score=0.7)
        examples = DemoSelector.diverse(collector.get_passing(), k=2)
        assert len(examples) == 2

    def test_optimizer_optimize(self):
        from core.prompt_optimizer import PromptOptimizer, Signature
        opt = PromptOptimizer()
        sig = Signature(name="plan", instruction="Plan a route", input_fields=["destination"])

        opt.record("plan", {"destination": "A"}, "go north", score=0.9)
        opt.record("plan", {"destination": "B"}, "go south", score=0.8)
        opt.record("plan", {"destination": "C"}, "fail", score=0.1)

        optimized = opt.optimize(sig, strategy="top_k", k=2)
        assert len(optimized.examples) == 2
        assert optimized.examples[0].score >= 0.8

    def test_optimizer_no_traces(self):
        from core.prompt_optimizer import PromptOptimizer, Signature
        opt = PromptOptimizer()
        sig = Signature(name="empty", instruction="test")
        result = opt.optimize(sig)
        assert result is sig


# ── Knowledge Graph Memory ──────────────────────────────────────

class TestKnowledgeGraph:
    def test_import(self):
        from core.graph_memory import KnowledgeGraph, Entity, Triple
        assert KnowledgeGraph is not None

    def test_add_entity(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        e = graph.add_entity("LiDAR", entity_type="sensor", properties={"range_m": 200})
        assert e.name == "LiDAR"
        assert e.entity_type == "sensor"
        assert len(graph) == 1

    def test_add_entity_dedup(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        e1 = graph.add_entity("Camera")
        e2 = graph.add_entity("camera")
        assert e1.entity_id == e2.entity_id
        assert len(graph) == 1

    def test_add_relation(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_entity("Car", "vehicle")
        graph.add_entity("LiDAR", "sensor")
        rel = graph.add_relation("Car", "has_sensor", "LiDAR")
        assert rel.relation_type == "has_sensor"
        stats = graph.stats()
        assert stats["entities"] == 2
        assert stats["relations"] == 1

    def test_add_triple(self):
        from core.graph_memory import KnowledgeGraph, Triple
        graph = KnowledgeGraph()
        t = Triple(subject="Driver", predicate="prefers", obj="Highway")
        graph.add_triple(t)
        assert len(graph) == 2

    def test_neighbors(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_relation("A", "connects", "B")
        graph.add_relation("B", "connects", "C")
        result = graph.neighbors("A", hops=1)
        names = {e.name for e in result.entities}
        assert "B" in names
        assert "C" not in names

    def test_neighbors_2_hops(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_relation("A", "to", "B")
        graph.add_relation("B", "to", "C")
        result = graph.neighbors("A", hops=2)
        names = {e.name for e in result.entities}
        assert "C" in names

    def test_find_path(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_relation("Start", "road", "Mid")
        graph.add_relation("Mid", "road", "End")
        path = graph.find_path("Start", "End")
        assert path is not None
        assert "Start" in path
        assert "End" in path

    def test_find_path_no_connection(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_entity("A")
        graph.add_entity("B")
        assert graph.find_path("A", "B") is None

    def test_search(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_entity("Front Camera", "sensor")
        graph.add_entity("Rear Camera", "sensor")
        graph.add_entity("GPS Module", "navigation")
        results = graph.search("camera")
        assert len(results) == 2

    def test_search_by_type(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_entity("Camera", "sensor")
        graph.add_entity("GPS", "navigation")
        results = graph.search("", entity_type="sensor")
        assert len(results) == 1

    def test_get_relations_for(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_relation("Car", "has", "Engine")
        graph.add_relation("Car", "has", "Wheels")
        rels = graph.get_relations_for("Car")
        assert len(rels) == 2

    def test_remove_entity(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_relation("A", "to", "B")
        assert graph.remove_entity("A")
        assert graph.get_entity("A") is None
        assert len(graph) == 1

    def test_decay(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        e = graph.add_entity("old_node")
        e.updated_at = 0
        e.access_count = 0
        removed = graph.decay(max_age_seconds=1)
        assert removed == 1
        assert len(graph) == 0

    def test_export_import_json(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_relation("A", "knows", "B")
        graph.add_entity("C", "test")
        json_str = graph.export_json()
        restored = KnowledgeGraph.from_json(json_str)
        assert len(restored) == 3
        assert restored.stats()["relations"] == 1

    def test_max_entities_eviction(self):
        from core.graph_memory import KnowledgeGraph
        graph = KnowledgeGraph(max_entities=5)
        for i in range(10):
            graph.add_entity(f"node_{i}")
        assert len(graph) <= 5
