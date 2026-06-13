"""
Tests for new GitHub-inspired features:
- EventStream (OpenHands event-sourcing)
- HandoffManager (LangGraph/OpenAI handoff protocol)
- Tracer (OTel-inspired tracing)
"""
import json
import time
import pytest


# ── EventStream ──────────────────────────────────────────────────

class TestEventStream:
    def test_import(self):
        from core.event_stream import EventStream, EventType, Event
        assert EventStream is not None

    def test_emit_and_query(self):
        from core.event_stream import EventStream, EventType
        stream = EventStream(agent_id="test")
        stream.emit(EventType.AGENT_START, {"task": "hello"})
        stream.emit(EventType.LLM_REQUEST, {"model": "gpt-4"})
        stream.emit(EventType.LLM_RESPONSE, {"tokens": 100})
        assert len(stream) == 3

    def test_subscribe(self):
        from core.event_stream import EventStream, EventType
        stream = EventStream()
        received = []
        stream.subscribe(EventType.TOOL_CALL, lambda e: received.append(e))
        stream.emit(EventType.TOOL_CALL, {"tool": "search"})
        stream.emit(EventType.LLM_REQUEST, {"model": "x"})
        assert len(received) == 1
        assert received[0].data["tool"] == "search"

    def test_snapshot_restore(self):
        from core.event_stream import EventStream, EventType
        stream = EventStream()
        stream.emit(EventType.AGENT_START, {})
        stream.snapshot("before_plan")
        stream.emit(EventType.ACTION_PLAN, {"steps": 3})
        stream.emit(EventType.ACTION_EXECUTE, {"tool": "x"})
        events_since = stream.restore("before_plan")
        assert len(events_since) == 2

    def test_query_by_type(self):
        from core.event_stream import EventStream, EventType
        stream = EventStream()
        stream.emit(EventType.SAFETY_CHECK, {"risk": 0.1})
        stream.emit(EventType.LLM_REQUEST, {})
        stream.emit(EventType.SAFETY_VIOLATION, {"rule": "x"})
        safety = stream.query(event_types=[EventType.SAFETY_CHECK, EventType.SAFETY_VIOLATION])
        assert len(safety) == 2

    def test_export_import_json(self):
        from core.event_stream import EventStream, EventType
        stream = EventStream()
        stream.emit(EventType.AGENT_START, {"task": "test"})
        stream.emit(EventType.AGENT_COMPLETE, {"result": "ok"})
        json_str = stream.export_json()
        restored = EventStream.from_json(json_str)
        assert len(restored) == 2

    def test_summary(self):
        from core.event_stream import EventStream, EventType
        stream = EventStream()
        stream.emit(EventType.LLM_REQUEST, {})
        stream.emit(EventType.LLM_RESPONSE, {})
        stream.emit(EventType.LLM_REQUEST, {})
        summary = stream.summary()
        assert summary["total_events"] == 3
        assert summary["event_types"]["llm_request"] == 2

    def test_max_events_cap(self):
        from core.event_stream import EventStream, EventType
        stream = EventStream(max_events=5)
        for i in range(10):
            stream.emit(EventType.LLM_REQUEST, {"i": i})
        assert len(stream) == 5


# ── Handoff Protocol ─────────────────────────────────────────────

class TestHandoffProtocol:
    def test_import(self):
        from core.handoff import HandoffManager, AgentCard, AgentRegistry
        assert HandoffManager is not None

    def test_agent_card_matches(self):
        from core.handoff import AgentCard
        card = AgentCard(
            agent_id="nav",
            name="Navigator",
            description="Handles navigation",
            capabilities=["path planning", "waypoint navigation", "obstacle avoidance"],
        )
        assert card.matches("path planning") is True
        assert card.matches("cooking") is False

    def test_registry_discover(self):
        from core.handoff import AgentRegistry, AgentCard
        reg = AgentRegistry()
        reg.register(AgentCard(
            agent_id="nav", name="Navigator", description="nav",
            capabilities=["navigation", "path planning"],
        ))
        reg.register(AgentCard(
            agent_id="sensor", name="Sensor", description="sensor",
            capabilities=["lidar", "camera", "sensor fusion"],
        ))
        results = reg.discover("path planning")
        assert len(results) == 1
        assert results[0].agent_id == "nav"

    def test_handoff_lifecycle(self):
        from core.handoff import HandoffManager, AgentCard, HandoffStatus
        mgr = HandoffManager()
        mgr.registry.register(AgentCard(
            agent_id="planner", name="Planner", description="plans",
            capabilities=["planning"],
        ))
        req = mgr.create_handoff("main", "planner", "plan a route")
        assert req.status == HandoffStatus.PENDING
        mgr.accept(req.handoff_id)
        assert req.status == HandoffStatus.ACCEPTED
        result = mgr.complete(req.handoff_id, result={"route": [1, 2, 3]})
        assert result.status == HandoffStatus.COMPLETED
        assert result.output == {"route": [1, 2, 3]}

    def test_auto_route(self):
        from core.handoff import HandoffManager, AgentCard
        mgr = HandoffManager()
        mgr.registry.register(AgentCard(
            agent_id="expert", name="Expert", description="expert",
            capabilities=["analysis", "diagnosis"],
            priority=10,
        ))
        req = mgr.auto_route("main", "run analysis on sensor data")
        assert req is not None
        assert req.target_agent == "expert"

    def test_auto_route_no_match(self):
        from core.handoff import HandoffManager
        mgr = HandoffManager()
        req = mgr.auto_route("main", "unknown task xyz")
        assert req is None

    def test_reject_handoff(self):
        from core.handoff import HandoffManager, HandoffStatus
        mgr = HandoffManager()
        req = mgr.create_handoff("a", "b", "task")
        assert mgr.reject(req.handoff_id, "busy") is True
        assert req.status == HandoffStatus.REJECTED

    def test_history(self):
        from core.handoff import HandoffManager
        mgr = HandoffManager()
        mgr.create_handoff("a", "b", "task1")
        mgr.create_handoff("a", "c", "task2")
        history = mgr.get_history()
        assert len(history) == 2


# ── Tracing ──────────────────────────────────────────────────────

class TestTracing:
    def test_import(self):
        from core.tracing import Tracer, SpanKind, get_tracer
        assert Tracer is not None

    def test_span_context_manager(self):
        from core.tracing import Tracer, SpanKind
        tracer = Tracer()
        with tracer.span("test_op", SpanKind.AGENT) as s:
            s.set_attribute("task", "hello")
        spans = tracer.get_spans()
        assert len(spans) == 1
        assert spans[0].name == "test_op"
        assert spans[0].attributes["task"] == "hello"

    def test_nested_spans(self):
        from core.tracing import Tracer, SpanKind
        tracer = Tracer()
        with tracer.span("parent", SpanKind.AGENT) as parent:
            with tracer.span("child", SpanKind.TOOL) as child:
                child.set_attribute("tool", "search")
        spans = tracer.get_spans()
        assert len(spans) == 2
        child_span = spans[0]
        parent_span = spans[1]
        assert child_span.parent_id == parent_span.span_id

    def test_trace_decorator(self):
        from core.tracing import Tracer, SpanKind
        tracer = Tracer()

        @tracer.trace(kind=SpanKind.TOOL, name="my_tool")
        def do_work(x, y):
            return x + y

        result = do_work(1, 2)
        assert result == 3
        spans = tracer.get_spans()
        assert len(spans) == 1
        assert spans[0].name == "my_tool"

    def test_error_tracking(self):
        from core.tracing import Tracer, SpanKind, SpanStatus
        tracer = Tracer()
        with pytest.raises(ValueError):
            with tracer.span("failing", SpanKind.INTERNAL) as s:
                raise ValueError("test error")
        spans = tracer.get_spans()
        assert spans[0].status == SpanStatus.ERROR
        assert "test error" in spans[0].error

    def test_llm_usage(self):
        from core.tracing import Tracer, SpanKind
        tracer = Tracer()
        with tracer.span("llm_call", SpanKind.LLM) as s:
            tracer.record_llm_usage("gpt-4", prompt_tokens=100, completion_tokens=50)
        summary = tracer.summary()
        assert summary["token_usage"]["prompt_tokens"] == 100
        assert summary["token_usage"]["total_tokens"] == 150

    def test_summary(self):
        from core.tracing import Tracer, SpanKind
        tracer = Tracer()
        with tracer.span("a", SpanKind.AGENT):
            pass
        with tracer.span("b", SpanKind.TOOL):
            pass
        with tracer.span("c", SpanKind.TOOL):
            pass
        summary = tracer.summary()
        assert summary["total_spans"] == 3
        assert summary["by_kind"]["tool"]["count"] == 2

    def test_export_json(self):
        from core.tracing import Tracer, SpanKind
        tracer = Tracer()
        with tracer.span("test", SpanKind.AGENT):
            pass
        json_str = tracer.export_json()
        data = json.loads(json_str)
        assert data["service"] == "Nonull"
        assert len(data["spans"]) == 1

    def test_disabled_tracer(self):
        from core.tracing import Tracer, SpanKind
        tracer = Tracer(enabled=False)
        with tracer.span("noop", SpanKind.AGENT) as s:
            s.set_attribute("x", 1)
        assert len(tracer.get_spans()) == 0

    def test_build_tree(self):
        from core.tracing import Tracer, SpanKind
        tracer = Tracer()
        with tracer.span("root", SpanKind.AGENT):
            with tracer.span("child1", SpanKind.TOOL):
                pass
            with tracer.span("child2", SpanKind.LLM):
                pass
        tree = tracer.build_tree()
        assert len(tree) == 1
        assert len(tree[0]["children"]) == 2

    def test_global_tracer(self):
        from core.tracing import get_tracer
        t1 = get_tracer()
        t2 = get_tracer()
        assert t1 is t2
