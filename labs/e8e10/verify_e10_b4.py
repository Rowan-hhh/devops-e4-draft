"""Run the independent E10 B4 acceptance gate from the merged main branch."""
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from lab import buildchecker, run, save, validate


EXPECTED_BRANCH = "e10-xzt-b4"


def source_state(project):
    project = Path(project)
    tracked = run(["git", "ls-files", "-z"], project).split("\0")
    return {
        "head": run(["git", "rev-parse", "HEAD"], project).strip(),
        "status": run(
            ["git", "status", "--porcelain", "--untracked-files=all"], project
        ),
        "sha256": {
            name: hashlib.sha256((project / name).read_bytes()).hexdigest()
            for name in tracked
            if name
        },
    }


def clone_input(bundle, destination):
    subprocess.run(
        ["git", "clone", str(Path(bundle).resolve()), str(Path(destination).resolve())],
        check=True,
        text=True,
        capture_output=True,
    )


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(out, repository):
    out = Path(out).resolve()
    repository = Path(repository).resolve()
    out.mkdir(parents=True, exist_ok=False)

    branch = run(["git", "branch", "--show-current"], repository).strip()
    head = run(["git", "rev-parse", "HEAD"], repository).strip()
    require(branch == EXPECTED_BRANCH, f"unexpected branch: {branch}")
    require(
        (repository / "reports/E10/B1/project.bundle").is_file(),
        "missing B1 project bundle",
    )

    bundle = repository / "reports/E10/B1/project.bundle"
    candidate = repository / "reports/E10/B3/candidate.patch"
    compile_failure = repository / "reports/E10/B2/compile-failure.patch"
    source_snapshot = repository / "reports/E10/B3/source-before.Makefile"
    require(candidate.is_file(), "missing B3 candidate patch")
    require(compile_failure.is_file(), "missing B2 compile-failure patch")
    require(source_snapshot.is_file(), "missing B3 source snapshot")

    project = out / "project"
    clone_input(bundle, project)
    before = source_state(project)
    before_makefile = (project / "Makefile").read_bytes()
    require(before["status"] == "", "restored project is not clean")
    require(before_makefile == source_snapshot.read_bytes(), "B3 source snapshot mismatch")

    rows = []

    wrong_test = validate(project, candidate, out / "reject-test", fail_test=True)
    require(
        not wrong_test["accepted"]
        and wrong_test["rollback"]
        and wrong_test["source_unchanged"],
        "wrong-test rejection failed",
    )
    rows.append({"case": "wrong-test", "passed": True})

    accepted = validate(project, candidate, out / "accept")
    require(accepted["accepted"] and all(accepted["checks"].values()), "accept failed")
    rows.append({"case": "accepted", "passed": True})

    broken = out / "broken.patch"
    broken.write_text("invalid patch\n", encoding="utf-8")
    bad_patch = validate(project, broken, out / "reject-patch")
    require(
        not bad_patch["accepted"]
        and bad_patch["rollback"]
        and bad_patch["source_unchanged"],
        "bad-patch rejection failed",
    )
    rows.append({"case": "bad-patch", "passed": True})

    compile_project = out / "compile-failure-project"
    clone_input(bundle, compile_project)
    compile_failure_result = validate(
        compile_project,
        compile_failure,
        out / "reject-compile",
    )
    require(
        not compile_failure_result["accepted"]
        and compile_failure_result["rollback"]
        and compile_failure_result["source_unchanged"],
        "compile-failure rejection failed",
    )
    rows.append({"case": "compile-failure", "passed": True})

    recheck_dir = out / "recheck-buildchecker"
    buildchecker(project, recheck_dir)
    recheck = json.loads((recheck_dir / "findings.json").read_text())
    require(recheck["status"] == "SUCCEEDED", "BuildChecker recheck failed")
    require(
        not any(item["type"] == "MISSING" for item in recheck["findings"]),
        "recheck still reports MISSING",
    )

    final_state = source_state(project)
    require(final_state["status"] == " M Makefile\n", "accepted source state unexpected")

    with (out / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["case", "passed"])
        writer.writeheader()
        writer.writerows(rows)

    command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "labs/e8e10", "-p", "test_profile.py", "-v"]
    tests = subprocess.run(command, cwd=repository, text=True, capture_output=True)
    (out / "unit-tests.log").write_text(tests.stdout + tests.stderr, encoding="utf-8")
    (out / "unit-tests-exit-code.txt").write_text(str(tests.returncode) + "\n", encoding="utf-8")
    require(tests.returncode == 0, "unit tests failed")

    result = {
        "schema_version": 1,
        "stage": "E10",
        "track": "B",
        "role": "B4",
        "branch": branch,
        "execution_commit": head,
        "input": {
            "b1_bundle": "reports/E10/B1/project.bundle",
            "b2_validation": "reports/E10/B2/241880179-handoff.json",
            "b3_candidate": "reports/E10/B3/candidate.patch",
        },
        "cases": rows,
        "accepted_checks": accepted["checks"],
        "recheck": {
            "status": recheck["status"],
            "missing_count": sum(item["type"] == "MISSING" for item in recheck["findings"]),
            "directory": "recheck-buildchecker",
        },
        "source": {
            "before_sha256": hashlib.sha256(before_makefile).hexdigest(),
            "after_accept_sha256": hashlib.sha256((project / "Makefile").read_bytes()).hexdigest(),
            "rejected_cases_preserved_source": True,
        },
        "unit_tests": {"count": 0, "exit_code": tests.returncode, "log": "unit-tests.log"},
        "passed": True,
    }
    for line in (tests.stdout + tests.stderr).splitlines():
        if line.startswith("Ran ") and " tests" in line:
            result["unit_tests"]["count"] = int(line.split()[1])
            break
    save(out / "acceptance.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[2]
    result = verify(args.out, repository)
    print("E10_B4_PASS", len(result["cases"]), "cases", result["unit_tests"])


if __name__ == "__main__":
    main()
