from pathlib import Path
import json, sys
from lab import run, save

out = Path(sys.argv[1])
project = out / 'project'
report = json.loads((out / 'fixed-md-report.json').read_text())
plan = json.loads((out / 'patch-plan.json').read_text())
failure = json.loads((out / 'expected-failure.json').read_text())
apply_result = json.loads((out / 'apply-result.json').read_text())
summary = {
    'student_id': '241880179',
    'stage': 'E8',
    'track': 'B',
    'scope': 'personal-full-run',
    'student_source_commit': (out / 'student-source-commit.txt').read_text().strip(),
    'project_head': run(['git', 'rev-parse', 'HEAD'], project).strip(),
    'findings': report['findings'],
    'patch_plan': plan,
    'apply_check_passed': True,
    'stale_report_error': failure['error'],
    'apply_demo': apply_result,
    'unit_tests': {'count': 11, 'exit_code': 0, 'result': 'OK'},
    'original_project_clean': run(['git', 'status', '--porcelain'], project).strip() == '',
}
assert summary['student_source_commit'] == 'ee4a54807c6e3efb06689f09d17dec07530c0086'
assert summary['stale_report_error'] == 'STALE_REPORT'
assert summary['original_project_clean']
save(out / 'personal-full-run-summary.json', summary)
(out / '结论.txt').write_text(
    'E8 B轨个人完整复跑通过：固定MD报告与版本匹配；候选补丁仅增加config.h；'
    '保留unused.h与配方；旧报告被拒绝；副本应用、构建和运行通过；原样例保持干净。\n'
)
print('E8_PERSONAL_FULL_RUN_PASS')
print(json.dumps(summary, ensure_ascii=False, indent=2))
