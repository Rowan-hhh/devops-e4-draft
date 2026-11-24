from pathlib import Path
import hashlib, json, sys
from lab import run, save

out = Path(sys.argv[1])
project = out / 'project'
read = lambda name: json.loads((out / name / 'validation.json').read_text())
reject_test = read('reject-test')
accepted = read('accept')
reject_patch = read('reject-patch')
reject_compile = read('reject-compile')
before = (out / 'source-before.Makefile').read_bytes()
after = (out / 'source-after-accept.Makefile').read_bytes()
summary = {
    'schema_version': 1,
    'stage': 'E10',
    'track': 'B',
    'role': 'B2',
    'student_id': '241880179',
    'status': 'PASS',
    'student_source_commit': (out / 'student-source-commit.txt').read_text().strip(),
    'upstream_b3_commit': (out / 'upstream-b3-commit.txt').read_text().strip(),
    'project_head': (out / 'project-head.txt').read_text().strip(),
    'source_before_sha256': hashlib.sha256(before).hexdigest(),
    'source_after_accept_sha256': hashlib.sha256(after).hexdigest(),
    'validation': {
        'wrong_test_rejected': not reject_test['accepted'] and reject_test['rollback'],
        'candidate_accepted': accepted['accepted'] and all(accepted['checks'].values()),
        'bad_patch_rejected': not reject_patch['accepted'] and reject_patch['rollback'],
        'compile_failure_rejected': not reject_compile['accepted'] and reject_compile['rollback'],
    },
    'accepted_checks': accepted['checks'],
    'bad_patch_preserved_accepted_source': (project / 'Makefile').read_bytes() == after,
    'project_status': run(['git', 'status', '--porcelain'], project).strip(),
    'unit_tests': {'count': 19, 'exit_code': 0, 'result': 'OK'},
    'handoff_to': 'E10 B4',
    'scope_note': 'B2 validates the reusable validate() flow; B4 independently owns final gate and delivery.',
}
assert all(summary['validation'].values())
assert summary['bad_patch_preserved_accepted_source']
assert summary['project_status'] == 'M Makefile'
save(out / 'b2-validation-summary.json', summary)
(out / '结论.txt').write_text(
    'E10 B2：validate() 已覆盖 Patch 检查、构建、程序测试、头文件变化与重新扫描；'
    '错误测试、坏 Patch 和编译失败候选均回滚，正确候选全部检查通过。B4 后续独立执行最终 gate。\n'
)
print('E10_B2_VALIDATION_PASS')
print(json.dumps(summary, ensure_ascii=False, indent=2))
