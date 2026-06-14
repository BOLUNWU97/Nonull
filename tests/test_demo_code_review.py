"""
code_review_demo smoke test / import check.

验证 demo 脚本语法 + 依赖正确 (能 import), 不跑 main() 避免误触真实 LLM。
Verifies the demo script imports cleanly (syntax + deps OK); does NOT run
main() to avoid triggering a real LLM call.
"""
import importlib.util

DEMO_PATH = "examples/code_review_demo.py"


def test_demo_imports_cleanly():
    """demo 能 import: 语法正确, 依赖 (from core import Nonull) 成立."""
    spec = importlib.util.spec_from_file_location("code_review_demo", DEMO_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # __main__ guard 阻止运行 main()
    assert callable(mod.main)
    assert isinstance(mod.SAMPLE_CODE, str)
    assert len(mod.SAMPLE_CODE) > 0
    # 示例代码含故意 bug (divide 无零检查)
    assert "def divide" in mod.SAMPLE_CODE
