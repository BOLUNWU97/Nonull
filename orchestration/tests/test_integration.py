"""Integration test for the orchestration package."""
import sys
sys.path.insert(0, r'C:\Users\EDY\Desktop\智能体')

from orchestration import (
    AgentType, AgentStatus, ConflictRecord, ConflictSeverity,
    SubtaskStatus, Message, MessageType,
    create_orchestrator, create_agent_pool, create_workflow_registry,
    create_communication_layer,
)
print('1. All imports OK')

# ============================================================
# Test: Orchestrator
# ============================================================
orch = create_orchestrator()
print(f'2. Orchestrator: {type(orch).__name__}')

# Test task decomposition
plan = orch.decompose_task('Review ADAS brake controller C++ code')
levels = plan.topological_order()
print(f'3. Plan: {plan.id[:8]}, {len(plan.subtasks)} subtasks, {len(levels)} levels')

# ============================================================
# Test: Agent Pool with all types
# ============================================================
pool = create_agent_pool(pre_spawn_agents=[
    AgentType.CODE_REVIEWER,
    AgentType.SAFETY_ANALYST,
    AgentType.TEST_ENGINEER,
    AgentType.DATA_ANALYST,
    AgentType.RESEARCH_AGENT,
    AgentType.DEVOPS_AGENT,
    AgentType.ORCHESTRATOR,
])
stats = pool.get_load_stats()
print(f'4. Pool: {stats["total_agents"]} agents')

# Test capability-based selection
agent_id = pool.select_agent({'c++_review', 'misra_check'})
print(f'5. Agent selected: {agent_id[:8]} ({pool.get_agent(agent_id).agent_type.value})')

# ============================================================
# Test: Workflow Registry
# ============================================================
registry = create_workflow_registry()
wfs = registry.list_workflows()
print(f'6. Registry: {len(wfs)} workflows')
for wf in wfs:
    print(f'   - {wf.id} ({len(wf.steps)} steps)')

# ============================================================
# Test: EventBus
# ============================================================
bus, ws = create_communication_layer()
msgs = []
bus.subscribe('safety', lambda m: msgs.append(m))
bus.publish(Message(type=MessageType.SYSTEM_EVENT, sender='test',
                    recipient='safety', payload={'alert': 'test'}))
print(f'7. EventBus: {len(msgs)} message delivered')

# ============================================================
# Test: SharedWorkspace
# ============================================================
ws.write('/agents/cr1/result', {'passed': True})
ws.write('/agents/cr2/result', {'passed': False})
r = ws.read('/agents/cr1/result')
entries = ws.list('/agents/')
print(f'8. Workspace: read={r}, list_entries={len(entries)}')

# ============================================================
# Test: Plan Execution with mock assignment and executor
# ============================================================
# Register a mock assignment function that always returns a dummy agent
orch.register_assignment_fn(lambda subtask, ctx: 'mock-agent-001')

def fake_executor(subtask, agent_id):
    """Fake executor that simulates successful completion."""
    return {
        'assigned_to': agent_id,
        'status': 'completed',
        'result': f'{subtask.name} done',
    }

result = orch.execute_plan(plan, agent_pool_context=pool, executor_fn=fake_executor)
succeeded = sum(1 for s in result.subtask_results.values() if s.status == SubtaskStatus.SUCCEEDED)
total = len(result.subtask_results)
print(f'9. Execution: status={result.status}, '
      f'succeeded={succeeded}/{total}, duration={result.duration_ms:.0f}ms')
assert succeeded == total, f'Expected all {total} subtasks to succeed, got {succeeded}'

# ============================================================
# Test: Orchestrator Status
# ============================================================
status = orch.get_status()
print(f'10. Status: plans={status["total_plans"]}, completed={status["completed_executions"]}')

# ============================================================
# Test: Conflict Resolution (enum severity)
# ============================================================
conflict = ConflictRecord(
    subtask_id='test',
    task_id='test',
    conflicting_results={'a1': {'value': 1}, 'a2': {'value': 2}},
    severity=ConflictSeverity.MEDIUM,
    description='Test conflict between agents a1 and a2'
)
resolved = orch.resolve_conflict(conflict, strategy='merge')
print(f'11. Conflict resolution: {resolved}')

# ============================================================
# Test: Execution Graph
# ============================================================
graph = orch.get_execution_graph(plan.id)
print(f'12. Graph: {len(graph["nodes"])} nodes, {len(graph["edges"])} edges, '
      f'{len(graph["levels"])} levels')

# ============================================================
# Test: State persistence
# ============================================================
import tempfile, os
with tempfile.TemporaryDirectory() as tmpdir:
    manifest = orch.save_state(tmpdir)
    print(f'13. State saved: {os.path.isdir(tmpdir)} (manifest={os.path.basename(manifest)})')

# ============================================================
# Test: Agent lifecycle
# ============================================================
pool.assign_task(agent_id, 'task-123')
pool.complete_task(agent_id, 'task-123', execution_seconds=5.0, success=True)
agent = pool.get_agent(agent_id)
print(f'14. Agent lifecycle: tasks_completed={agent.total_tasks_completed}, '
      f'status={agent.status.value}')

# ============================================================
# Test: Workflow instantiation
# ============================================================
wf_plan = registry.instantiate('safety_analysis', 'Analyze braking system hazards')
levels2 = wf_plan.topological_order()
print(f'15. Workflow instantiation: {wf_plan.metadata["workflow_id"]}, '
      f'{len(wf_plan.subtasks)} steps, {len(levels2)} levels')

# ============================================================
# Test: EventBus stats
# ============================================================
bus_stats = bus.get_stats()
print(f'16. EventBus stats: {bus_stats["topics"]} topics, '
      f'{bus_stats["registered_agents"]} agents')

# ============================================================
# Test: Workspace history
# ============================================================
history = ws.get_history('/agents/cr1/result')
print(f'17. Workspace history: {len(history)} entries')

# ============================================================
print()
print('=== ALL 17 INTEGRATION TESTS PASSED ===')
