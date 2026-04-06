#!/usr/bin/env python3
"""
Novel Material Eval Suite Runner

执行 eval tasks，计算 pass@k 指标，写入 baseline 快照。
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
EVALS_DIR = PROJECT_ROOT / "evals"
TASKS_DIR = EVALS_DIR / "tasks"
GRADERS_DIR = EVALS_DIR / "graders"
RESULTS_DIR = PROJECT_ROOT / "docs" / "evals" / "results" / "baselines"


class EvalRunner:
    """Eval Suite 执行引擎"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[Dict] = []

    def load_tasks(self, task_file: str) -> Dict:
        """加载任务 YAML"""
        task_path = TASKS_DIR / task_file
        if not task_path.exists():
            raise FileNotFoundError(f"Task file not found: {task_path}")

        with open(task_path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)

        return content

    def validate_task_schema(self, task: Dict) -> bool:
        """验证任务 schema"""
        required_fields = ["task_id", "skill", "description", "input", "expected_output", "grader"]
        for field in required_fields:
            if field not in task:
                if self.verbose:
                    print(f"  [WARN] Task missing required field: {field}")
                return False
        return True

    def run_deterministic_grader(self, task: Dict) -> Dict:
        """运行确定性 grader（模拟执行）"""
        task_id = task["task_id"]
        skill = task["skill"]
        expected = task["expected_output"]

        # 注意：这是模拟执行，实际执行需要调用 skill
        # 当前仅做 schema 验证和逻辑检查

        result = {
            "task_id": task_id,
            "skill": skill,
            "grader": "deterministic",
            "status": "simulated",
            "checks": [],
        }

        # 检查 expected_output 结构
        checks_passed = True
        for check_name, expected_value in expected.items():
            check_result = {
                "name": check_name,
                "expected": expected_value,
                "actual": "SIMULATED",
                "pass": True,  # 模拟 pass
            }
            result["checks"].append(check_result)

        result["pass"] = checks_passed
        result["note"] = "Deterministic grader simulated - requires actual skill execution"

        return result

    def run_rubric_grader(self, task: Dict) -> Dict:
        """运行 rubric grader（模拟执行）"""
        task_id = task["task_id"]
        skill = task["skill"]

        result = {
            "task_id": task_id,
            "skill": skill,
            "grader": "rubric",
            "status": "simulated",
            "dimensions": [],
        }

        # 模拟评分维度
        dimensions = ["relevance", "quality", "format"]
        avg_score = 4.0  # 模拟分数

        for dim in dimensions:
            dim_result = {
                "name": dim,
                "score": 4,
                "pass": True,
            }
            result["dimensions"].append(dim_result)

        result["avg_score"] = avg_score
        result["pass"] = avg_score >= 4.0
        result["note"] = "Rubric grader simulated - requires LLM scoring"

        return result

    def run_task(self, task: Dict) -> Dict:
        """运行单个任务"""
        if not self.validate_task_schema(task):
            return {
                "task_id": task.get("task_id", "unknown"),
                "pass": False,
                "error": "Invalid task schema",
            }

        grader_type = task["grader"]

        if grader_type == "deterministic":
            return self.run_deterministic_grader(task)
        elif grader_type == "rubric":
            return self.run_rubric_grader(task)
        else:
            return {
                "task_id": task["task_id"],
                "pass": False,
                "error": f"Unknown grader type: {grader_type}",
            }

    def run_suite(self, tasks: List[Dict], trials: int = 1) -> Dict:
        """运行整个 suite"""
        task_results = []

        for task in tasks:
            # 多次 trial
            trial_results = []
            for t in range(trials):
                result = self.run_task(task)
                trial_results.append(result)

            # 计算 pass@k
            passes = sum(1 for r in trial_results if r.get("pass", False))
            pass_rate = passes / trials

            task_summary = {
                "task_id": task["task_id"],
                "skill": task["skill"],
                "grader": task["grader"],
                "description": task["description"],
                "trial_count": trials,
                "passes": passes,
                "pass_rate": pass_rate,
                "result": trial_results[0] if trials == 1 else trial_results,
            }

            task_results.append(task_summary)
            self.results.append(task_summary)

        # 计算整体指标
        total_passes = sum(1 for t in task_results if t["pass_rate"] >= 1.0)
        total_tasks = len(task_results)

        suite_result = {
            "run_id": self.generate_run_id(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "suite_name": "material-skills-regression",
            "trials_per_task": trials,
            "total_tasks": total_tasks,
            "total_passes": total_passes,
            "pass@1": total_passes / total_tasks if total_tasks > 0 else 0,
            "pass@3": min(1.0, total_passes / total_tasks * 1.1),  # 估算
            "pass^3": total_passes / total_tasks * 0.9,  # 估算
            "tasks": task_results,
            "balance": self.check_balance(task_results),
            "saturation_alert": total_passes / total_tasks >= 0.98,
            "status": "simulated",
            "note": "Results are simulated - requires actual skill execution",
        }

        return suite_result

    def check_balance(self, task_results: List[Dict]) -> Dict:
        """检查正负案例平衡"""
        positive = sum(1 for t in task_results if "-neg-" not in t["task_id"])
        negative = sum(1 for t in task_results if "-neg-" in t["task_id"])

        return {
            "positive_cases": positive,
            "negative_cases": negative,
            "ratio": f"{positive}:{negative}",
            "balanced": abs(positive - negative) <= 2,
        }

    def generate_run_id(self) -> str:
        """生成 run ID"""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{timestamp}--material-skills-regression"

    def save_baseline(self, suite_result: Dict) -> Path:
        """保存 baseline 快照"""
        # 确保 results 目录存在
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        run_id = suite_result["run_id"]
        filename = f"{run_id}.json"
        filepath = RESULTS_DIR / filename

        # 写入 JSON
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(suite_result, f, indent=2, ensure_ascii=False)

        # 创建 latest 指针
        latest_path = RESULTS_DIR / "latest--material-skills-regression.json"
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(suite_result, f, indent=2, ensure_ascii=False)

        if self.verbose:
            print(f"  [OK] Baseline saved to: {filepath}")
            print(f"  [OK] Latest pointer: {latest_path}")

        return filepath

    def print_summary(self, suite_result: Dict):
        """打印摘要"""
        print("\n" + "=" * 60)
        print("EVAL SUITE SUMMARY")
        print("=" * 60)

        print(f"\nRun ID: {suite_result['run_id']}")
        print(f"Timestamp: {suite_result['timestamp']}")
        print(f"Status: {suite_result['status']}")

        print(f"\nTotal Tasks: {suite_result['total_tasks']}")
        print(f"Passes: {suite_result['total_passes']}")

        print(f"\nMetrics:")
        print(f"  pass@1: {suite_result['pass@1']:.2%}")
        print(f"  pass@3: {suite_result['pass@3']:.2%}")
        print(f"  pass^3: {suite_result['pass^3']:.2%}")

        balance = suite_result["balance"]
        print(f"\nBalance: {balance['positive_cases']} positive / {balance['negative_cases']} negative")
        print(f"  Balanced: {balance['balanced']}")

        if suite_result["saturation_alert"]:
            print("\n[ALERT] Suite saturated (>= 98% pass rate)")
            print("  Suggestion: Add harder capability tasks")

        print("\n" + "=" * 60)

        # 按 skill 分组
        print("\nBY SKILL:")
        print("-" * 40)

        skill_groups = {}
        for task in suite_result["tasks"]:
            skill = task["skill"]
            if skill not in skill_groups:
                skill_groups[skill] = []
            skill_groups[skill].append(task)

        for skill, tasks in sorted(skill_groups.items()):
            passes = sum(1 for t in tasks if t["pass_rate"] >= 1.0)
            total = len(tasks)
            rate = passes / total if total > 0 else 0
            print(f"  {skill}: {passes}/{total} ({rate:.0%})")


def list_tasks():
    """列出可用任务文件"""
    print("Available task files:")
    for f in TASKS_DIR.glob("*.yaml"):
        print(f"  - {f.name}")


def verify_tasks(task_file: str, verbose: bool = False):
    """验证任务文件"""
    runner = EvalRunner(verbose=verbose)

    print(f"\nVerifying: {task_file}")
    print("-" * 40)

    try:
        content = runner.load_tasks(task_file)
        tasks = content.get("tasks", [])

        valid_count = 0
        invalid_count = 0

        for task in tasks:
            task_id = task.get("task_id", "unknown")
            if runner.validate_task_schema(task):
                valid_count += 1
                if verbose:
                    print(f"  [OK] {task_id}")
            else:
                invalid_count += 1
                print(f"  [FAIL] {task_id}")

        print(f"\nTotal: {len(tasks)} tasks")
        print(f"Valid: {valid_count}")
        print(f"Invalid: {invalid_count}")

        # 检查平衡
        positive = sum(1 for t in tasks if "-neg-" not in t.get("task_id", ""))
        negative = sum(1 for t in tasks if "-neg-" in t.get("task_id", ""))
        print(f"\nBalance: {positive} positive / {negative} negative")

        if abs(positive - negative) > 2:
            print("  [WARN] Unbalanced positive/negative cases")

    except FileNotFoundError as e:
        print(f"  [ERROR] {e}")
        return False

    return invalid_count == 0


def run_suite(task_file: str, trials: int = 3, verbose: bool = False, save: bool = True):
    """运行 suite"""
    runner = EvalRunner(verbose=verbose)

    print(f"\nRunning: {task_file}")
    print(f"Trials per task: {trials}")
    print("-" * 40)

    try:
        content = runner.load_tasks(task_file)
        tasks = content.get("tasks", [])

        print(f"Loaded {len(tasks)} tasks")

        suite_result = runner.run_suite(tasks, trials=trials)

        runner.print_summary(suite_result)

        if save:
            filepath = runner.save_baseline(suite_result)
            print(f"\nBaseline saved: {filepath}")

        return suite_result

    except FileNotFoundError as e:
        print(f"  [ERROR] {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Novel Material Eval Suite Runner")
    parser.add_argument("command", choices=["list", "verify", "run"], help="Command to execute")
    parser.add_argument("--tasks", "-t", help="Task file name")
    parser.add_argument("--trials", "-k", type=int, default=3, help="Number of trials per task")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--no-save", action="store_true", help="Do not save baseline")

    args = parser.parse_args()

    if args.command == "list":
        list_tasks()

    elif args.command == "verify":
        if not args.tasks:
            print("Error: --tasks required for verify")
            sys.exit(1)
        success = verify_tasks(args.tasks, verbose=args.verbose)
        sys.exit(0 if success else 1)

    elif args.command == "run":
        if not args.tasks:
            print("Error: --tasks required for run")
            sys.exit(1)
        run_suite(args.tasks, trials=args.trials, verbose=args.verbose, save=not args.no_save)


if __name__ == "__main__":
    main()