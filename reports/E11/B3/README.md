# E11 B3 交付记录

## 职责与版本

B3 负责五类契约异常拒绝、错误码和无修复写入证据，并补充 macro/mixed 声明风格测试。

- 学号：241880360；角色：E11 B3；分支：`student/241880360/e11-b3`。
- B2 合并基线：`a091cd9da6e90192e9b411ec7c6503ca3211ab29`；B3 实现及正式执行提交：`c061973fb7d33fd25a712a78ef103c5ea0babc01`。
- 上游 B2：PR #19，报告提交 `6ed7a9b`，固定 MD 与修复目标内部提交 `4350fcdafaf4e708f51ea95f018211085dcd73d2`；交接见 `reports/E11/B2/241880179-handoff.json`。
- 正式运行目录标识：`work/e11-B3-241880360-20261110-190133`。

B1 的 DRAFT 两轮构建交接见 `reports/E11/B1/README.md`、`ci-run.json`；B2 README 和 handoff 记录其消费的 B1 PR #18 交接及成功修复、验证、动态重检。本次不重做 B1/B2 流程。

## 契约异常结果

| case | 预期错误码 | 实际错误码 |
|---|---|---|
| old_commit | `STALE_REPORT` | `STALE_REPORT` |
| wrong_schema | `SCHEMA_MISMATCH` | `SCHEMA_MISMATCH` |
| wrong_kind | `ARTIFACT_TYPE_MISMATCH` | `ARTIFACT_TYPE_MISMATCH` |
| changed_artifact | `ARTIFACT_HASH_MISMATCH` | `ARTIFACT_HASH_MISMATCH` |
| failed_upstream | `UPSTREAM_FAILED` | `UPSTREAM_FAILED` |

五类异常均在调用 Patch 生成逻辑前拒绝，每项均为 `rejected=true`、`patch_generated=false`、`source_unchanged=true`、`output_unchanged=true`。各 result 的 `output_before` 与 `output_after` 均为 `{}`；源项目（含 Git 文件）的前后哈希清单一致。`output_unchanged` 指修复输出目录，不表示用于保存输入和验证结果的证据目录没有写入。

`summary.json` 为 `passed=true`、`cases=5`。服务器 `unit-tests.log` 记录 `Ran 12 tests`、`OK`，`unit-tests-exit-code.txt` 为 `0`。这些是服务器原始运行结果，本次仅归档与核验，没有重新执行正式实验。

## 独立扩展

独立扩展测试为 `StudentE11B3.test_two_missing_headers_patch_macro_and_mixed_styles`，以一个测试方法配合 `subTest` 覆盖 macro、mixed，每种样例均包含 `config.h`、`extra.h` 两项 MISSING。复用真实 fixture、scan、patch：macro 在 `DEPS` 变量声明补齐，mixed 保留 `$(HEADERS)` 并在 `main.o` 声明补齐。测试核对 recipe 字节不变、原样例初始 Git 状态为空且前后文件和状态一致；候选执行 `git apply --check`，实际应用仅发生在临时隔离副本，随后扫描无 MISSING，临时目录自动清理。

## 阶段边界

E11 仅做 B 组内部集成，使用 fixed-md 并对齐契约字段，不需要接收真实 A 组产物；真实 A/B 产物交换属于 E12。本次异常输入由验证脚本在受控 fixture 上实际构造，样例当前提交为 `f6d47304d10c01479ba78a38f76aa745c7510617`，old_commit 使用其父提交 `881535c507e281dde6ce475ba9361af59879b62b`，并非直接重放 B2 的修复目标。B3 不重复生成 B2 已验证的正式正确候选，也不在本归档生成新的 candidate.patch。

## 原始证据索引

以下 17 个文件保留服务器复制来的原始字节；归档前后已核对 SHA-256。

- `changed_artifact/input.json`
- `changed_artifact/result.json`
- `environment.txt`
- `failed_upstream/input.json`
- `failed_upstream/result.json`
- `old_commit/input.json`
- `old_commit/result.json`
- `source-after.json`
- `source-before.json`
- `student-source-commit.txt`
- `summary.json`
- `unit-tests-exit-code.txt`
- `unit-tests.log`
- `wrong_kind/input.json`
- `wrong_kind/result.json`
- `wrong_schema/input.json`
- `wrong_schema/result.json`

五个 case 的 input/result 分别保存异常输入与实际拒绝结果；summary 汇总验证结论；source-before/after 是源文件哈希证据；environment、student-source-commit 和 unit-tests 文件分别记录环境、执行版本与完整测试。

## 向 B4 交接

交接对象为 E11 B4。入口为本目录 `241880360-handoff.json`；`archive-manifest.json` 覆盖除自身外的全部文件，含本 README 和 handoff。B4 可据此核对 B2/B3 版本、五项错误码、无修复写入及 12 项测试结果，再完成组内汇总。个人文档见 `docs/students/241880360/e11-b3/`。本归档不新增 CI Run ID、B3 PR 编号或 Artifact。
