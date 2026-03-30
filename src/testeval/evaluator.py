"""Local evaluator for TestEval benchmark tasks.

Follows the same evaluation methodology as TestEval's evaluation scripts:
1. Syntax check via compile()
2. Test run via subprocess (sandboxed, with timeout)
3. Coverage measurement via pytest-cov

Uses subprocess isolation for safety -- consistent with our TestGenEval evaluator.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src.metrics import CoverageResult

_COVERAGERC = """\
[report]
exclude_also =
    import math
    import itertools
    import bisect
    import collections
    import string
    import heapq
    import functools
    import sortedcontainers
    import operator
    from typing import List, Dict, Tuple, Iterator*
    from math import sqrt
    from bisect import bisect_left*
    from dataclasses import dataclass
    import *
    from * import *
"""


def quick_execute(
    task: dict[str, Any],
    generated_test_code: str,
    timeout_s: int = 30,
) -> tuple[bool, str]:
    """Quick pass/fail check for TestEval tasks.

    Writes the Solution class as under_test.py and the generated tests
    as test_generated.py, then runs pytest.
    """
    with tempfile.TemporaryDirectory(prefix="testeval_") as tmpdir:
        _setup_test_dir(tmpdir, task, generated_test_code)
        result = _run_tests(tmpdir, timeout_s)
        return result["passed"], result.get("error", "")


def evaluate_tests(
    task: dict[str, Any],
    generated_test_code: str,
    timeout_s: int = 30,
) -> CoverageResult:
    """Run tests and measure coverage for a TestEval task."""
    with tempfile.TemporaryDirectory(prefix="testeval_") as tmpdir:
        _setup_test_dir(tmpdir, task, generated_test_code)

        exec_result = _run_tests(tmpdir, timeout_s)
        if not exec_result["passed"]:
            return CoverageResult(
                passed=False,
                error_message=exec_result["error"],
                tests_generated=exec_result["total"],
                tests_passed=exec_result["passed_count"],
            )

        cov_result = _run_with_coverage(tmpdir, timeout_s)
        return CoverageResult(
            passed=True,
            line_coverage=cov_result["line_coverage"],
            branch_coverage=cov_result["branch_coverage"],
            tests_generated=exec_result["total"],
            tests_passed=exec_result["passed_count"],
        )


def _strip_solution_redefinition(test_code: str) -> str:
    """Remove any re-defined Solution class from generated test code.

    Some LLMs copy the entire Solution class into the test file instead
    of importing it. This means coverage is measured against the local
    copy, not under_test.py, resulting in near-zero coverage. This
    function strips such redefinitions so the import is used instead.
    """
    # Match 'class Solution' block: from the class line to the next
    # top-level definition (def/class at indent 0) or end of string
    pattern = re.compile(
        r"^class Solution[^\n]*\n(?:(?:[ \t]+[^\n]*|[ \t]*)\n)*",
        re.MULTILINE,
    )
    cleaned = pattern.sub("", test_code)

    # Also remove standalone imports that only exist to support the
    # redefined class (the standard TestEval boilerplate)
    boilerplate_imports = [
        r"^import math\n",
        r"^import itertools\n",
        r"^import bisect\n",
        r"^import collections\n",
        r"^import string\n",
        r"^import heapq\n",
        r"^import functools\n",
        r"^import sortedcontainers\n",
        r"^from typing import List, Dict, Tuple, Iterator\n",
    ]
    # Only strip these if they appear before any test function
    first_test = cleaned.find("def test_")
    if first_test > 0:
        preamble = cleaned[:first_test]
        body = cleaned[first_test:]
        for pat in boilerplate_imports:
            preamble = re.sub(pat, "", preamble, flags=re.MULTILINE)
        cleaned = preamble + body

    return cleaned


def _setup_test_dir(
    tmpdir: str, task: dict[str, Any], test_code: str,
) -> None:
    """Write the code under test and test file into a temp directory."""
    tmp = Path(tmpdir)

    # Write the Solution class as the module under test
    (tmp / "under_test.py").write_text(task["code_src"])

    # Write .coveragerc to exclude import boilerplate
    (tmp / ".coveragerc").write_text(_COVERAGERC)

    # Strip any re-defined Solution class from the test code
    test_code = _strip_solution_redefinition(test_code)

    # Ensure the test code imports from under_test
    import_line = "from under_test import Solution\n"
    if "from under_test import" not in test_code:
        test_code = import_line + test_code

    (tmp / "test_generated.py").write_text(test_code)


def _run_tests(tmpdir: str, timeout_s: int) -> dict[str, Any]:
    """Run pytest and return pass/fail + counts."""
    try:
        result = subprocess.run(
            [
                "python3", "-m", "pytest",
                "test_generated.py",
                "-v", "--tb=short", "--no-header",
            ],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )

        output = result.stdout + result.stderr
        passed_count = output.count(" PASSED")
        failed_count = output.count(" FAILED")
        error_count = output.count(" ERROR")
        total = passed_count + failed_count + error_count

        if result.returncode == 0:
            return {"passed": True, "total": total, "passed_count": passed_count}

        return {
            "passed": False,
            "error": output[-2000:] if len(output) > 2000 else output,
            "total": total,
            "passed_count": passed_count,
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "error": f"Timed out after {timeout_s}s",
            "total": 0,
            "passed_count": 0,
        }
    except Exception as e:
        return {"passed": False, "error": str(e), "total": 0, "passed_count": 0}


def _run_with_coverage(tmpdir: str, timeout_s: int) -> dict[str, float]:
    """Run pytest with coverage and parse the JSON report."""
    try:
        subprocess.run(
            [
                "python3", "-m", "pytest",
                "test_generated.py",
                "--cov=under_test",
                "--cov-branch",
                "--cov-report=json:coverage.json",
                "-q",
            ],
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )

        cov_json = Path(tmpdir) / "coverage.json"
        if not cov_json.exists():
            return {"line_coverage": 0.0, "branch_coverage": 0.0}

        cov_data = json.loads(cov_json.read_text())
        totals = cov_data.get("totals", {})

        num_stmts = totals.get("num_statements", 0)
        covered_stmts = totals.get("covered_lines", 0)
        num_branches = totals.get("num_branches", 0)
        covered_branches = totals.get("covered_branches", 0)

        line_cov = covered_stmts / num_stmts if num_stmts > 0 else 0.0
        branch_cov = covered_branches / num_branches if num_branches > 0 else 0.0

        return {
            "line_coverage": round(line_cov, 4),
            "branch_coverage": round(branch_cov, 4),
        }
    except Exception:
        return {"line_coverage": 0.0, "branch_coverage": 0.0}
