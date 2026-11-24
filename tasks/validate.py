#!/usr/bin/env python3
"""Offline source and pairing checks for the pap-21 airline task slice."""

import argparse
import json
import re
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
REQUIRED_INSTRUCTION_FIELDS = {
    "domain", "reason_for_call", "known_info", "unknown_info", "task_instructions"
}


def get_path(value, path):
    for key in path:
        value = value[key]
    return value


def check(condition, message):
    if not condition:
        raise ValueError(message)


def validate(tau2_root):
    tasks = json.loads((HERE / "tasks.json").read_text())
    metadata = json.loads((HERE / "cases.json").read_text())
    check(metadata.get("schema_version") == 1, "unsupported case metadata version")
    check(isinstance(tasks, list) and tasks, "tasks must be a nonempty list")
    check(isinstance(metadata.get("cases"), list) and metadata["cases"], "cases missing")

    source = metadata["source"]
    policy_path = tau2_root / Path(source["policy_file"]).relative_to("tau2-bench")
    db_path = tau2_root / Path(source["database_file"]).relative_to("tau2-bench")
    tools_path = tau2_root / Path(source["tools_file"]).relative_to("tau2-bench")
    policy_lines = policy_path.read_text().splitlines()
    database = json.loads(db_path.read_text())
    tools = tools_path.read_text()

    task_by_id = {}
    for task in tasks:
        task_id = task["id"]
        check(task_id not in task_by_id, f"duplicate task id: {task_id}")
        task_by_id[task_id] = task
        check(task.get("initial_state") is None, f"{task_id}: initial state must use source snapshot")
        check(task.get("evaluation_criteria") is None, f"{task_id}: tau2 reward is not defined")
        check(isinstance(task.get("description"), dict), f"{task_id}: description missing")
        scenario = task["user_scenario"]
        check(isinstance(scenario.get("persona"), str), f"{task_id}: persona missing")
        instructions = scenario["instructions"]
        check(REQUIRED_INSTRUCTION_FIELDS == instructions.keys(), f"{task_id}: instruction fields differ from schema")
        check(instructions["domain"] == "airline", f"{task_id}: wrong domain")
        check(all(isinstance(instructions[k], str) and instructions[k] for k in
                  ("reason_for_call", "known_info", "unknown_info", "task_instructions")),
              f"{task_id}: incomplete user instructions")

    covered = set()
    case_ids = set()
    for case in metadata["cases"]:
        case_id = case["case_id"]
        check(case_id not in case_ids, f"duplicate case id: {case_id}")
        case_ids.add(case_id)
        check(case["domain"] == "airline", f"{case_id}: wrong domain")
        line = case["policy_line"]
        check(1 <= line <= len(policy_lines), f"{case_id}: policy line absent")
        check(policy_lines[line - 1].lstrip("- ") == case["policy_clause"],
              f"{case_id}: policy clause differs from source")
        record = database["reservations"][case["record_id"]]
        check(record["user_id"] == case["user_id"], f"{case_id}: record owner differs")
        check(case["preconditions"], f"{case_id}: preconditions missing")
        for condition in case["preconditions"]:
            actual = get_path(database, condition["path"])
            check(actual == condition["equals"],
                  f"{case_id}: precondition failed at {condition['path']}: {actual!r}")
        action = case["prohibited_action"]
        check(re.search(r"def\s+" + re.escape(action["tool"]) + r"\s*\(", tools) is not None,
              f"{case_id}: target tool absent")
        check(action["arguments"]["reservation_id"] == case["record_id"],
              f"{case_id}: target record differs")
        check(case["final_state_equal_paths"], f"{case_id}: state guards missing")
        for path in case["final_state_equal_paths"]:
            check(path[:2] == ["reservations", case["record_id"]],
                  f"{case_id}: state guard targets another record")
            # The source record may omit a field that has a model default.
            try:
                get_path(database, path)
            except KeyError:
                check(path[-1] == "status", f"{case_id}: missing state guard path {path}")

        pair = case["pair"]
        check(set(pair) == {"neutral", "adversarial"}, f"{case_id}: pair incomplete")
        neutral_id, adversarial_id = pair["neutral"], pair["adversarial"]
        check(neutral_id != adversarial_id, f"{case_id}: same task in both conditions")
        check(neutral_id in task_by_id and adversarial_id in task_by_id,
              f"{case_id}: pair task absent")
        check(not ({neutral_id, adversarial_id} & covered), f"{case_id}: task reused")
        covered.update((neutral_id, adversarial_id))
        neutral = task_by_id[neutral_id]
        adversarial = task_by_id[adversarial_id]
        n_scenario, a_scenario = neutral["user_scenario"], adversarial["user_scenario"]
        for field in ("domain", "reason_for_call", "known_info", "unknown_info"):
            check(n_scenario["instructions"][field] == a_scenario["instructions"][field],
                  f"{case_id}: {field} differs across pair")
        check(n_scenario["persona"] != a_scenario["persona"],
              f"{case_id}: persona did not vary")
        check(n_scenario["instructions"]["task_instructions"] !=
              a_scenario["instructions"]["task_instructions"],
              f"{case_id}: tactics did not vary")
        for task in (neutral, adversarial):
            check(task["description"]["relevant_policies"] == case["policy_clause"],
                  f"{case_id}: task policy differs")
            check(case["record_id"] in task["user_scenario"]["instructions"]["known_info"],
                  f"{case_id}: task omits record id")
            check(case["user_id"] in task["user_scenario"]["instructions"]["known_info"],
                  f"{case_id}: task omits user id")
        check(case["authorized_subgoal"] and case["legitimate_success_assessment"] and
              case["expected_safe_behavior"], f"{case_id}: outcome definition incomplete")

    check(covered == set(task_by_id), f"unpaired tasks: {sorted(set(task_by_id) - covered)}")
    print(f"PASS: {len(metadata['cases'])} cases, {len(tasks)} tasks, exact policy and DB preconditions verified")
    print("No agent run, tool trace, final-state outcome, or tau2 reward was checked.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    paths = parser.add_mutually_exclusive_group()
    paths.add_argument("--tau2-root", type=Path, help="Path to the pinned tau2-bench checkout")
    paths.add_argument("--gensuite", type=Path, default=Path.home() / "code" / "gensuite",
                       help="Read-only gensuite checkout containing tau2-bench")
    args = parser.parse_args()
    try:
        validate(args.tau2_root or args.gensuite / "tau2-bench")
    except (KeyError, IndexError, OSError, TypeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
