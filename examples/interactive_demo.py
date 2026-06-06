"""
Nonull Interactive Demo (no LLM required)

Shows 3 core workflows:
1. Code Review
2. Scenario Coverage
3. Skills Inventory

Usage: python examples/interactive_demo.py
"""


def demo_code_review():
    print("\n [1] Code Review")
    print("-" * 40)
    from skills.registry import SkillRegistry
    reg = SkillRegistry()
    reg.auto_discover()
    skill = reg.get_skill("code_review")
    if not skill:
        print("  Skill not found")
        return
    code = "float calc(float d) { if (d < 5.0) return 1.0; return 0.0; }"
    skill.activate()
    result = skill.execute({"code": code, "language": "cpp"})
    print(f"  Issues: {result.data.get('total_issues', 0)}")
    for i in result.data.get("issues", [])[:3]:
        print(f"    [{i.get('severity','?')}] {i.get('description','?')}")
    skill.deactivate()


def demo_scenarios():
    print("\n [2] Scenario Coverage")
    print("-" * 40)
    try:
        from domains.adas.scenarios import ScenarioEngine
    except ImportError:
        print("  ADAS domain not loaded")
        return
    engine = ScenarioEngine()
    cases = ["highway_cut_in", "urban_pedestrian"]
    report = engine.analyze_scenario_coverage(cases)
    print(f"  Coverage: {report.get('coverage_pct', '?')}%")
    print(f"  Missing:  {report.get('missing_scenarios', [])[:3]}")


def demo_skills():
    print("\n [3] Skills Inventory")
    print("-" * 40)
    from skills.registry import SkillRegistry
    reg = SkillRegistry()
    reg.auto_discover()
    skills = reg.get_all_skills()
    cats = {}
    for s in skills:
        c = s.metadata.category.value if hasattr(s.metadata.category, 'value') else str(s.metadata.category)
        cats.setdefault(c, []).append(s.metadata.name)
    print(f"  Total: {len(skills)} skills")
    for c, n in sorted(cats.items()):
        print(f"    {c}: {len(n)} ({', '.join(n[:2])}...)")


def main():
    demo_code_review()
    demo_scenarios()
    demo_skills()
    print("\n✅ Done")


if __name__ == "__main__":
    main()
