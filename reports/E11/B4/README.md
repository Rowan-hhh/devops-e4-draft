# E11 B4 最终验收记录

## 验收范围

- 负责人：谢真婷（学号 `241880610`）
- 角色：E11 B4，B 组内部集成与最终验收
- 分支：`e11-xzt-b4`
- 上游集成分支：`e11-e12-integration`
- 验收基线：`3e96221c3ab3d1c55dffedb6d5ee23f020c3af8e`

本次从最新 `e11-e12-integration` 开始，未从旧 `main` 开始。B4 只整合和核验 B1、B2、B3 已交付内容，不重写上游实现。

## 上游交付核对

| 模块 | 核对内容 | 结论 |
|---|---|---|
| B1 | DRAFT 两轮构建：第 1 轮 `MISSING_MAKE`，第 2 轮构建和运行成功，输出 `1` | 已有证据，保留原始日志 |
| B2 | 固定 MD、候选 Patch、repair plan、Patch 验证和动态重检 | 已有证据，候选 Patch 被接受 |
| B3 | 五类契约异常、无 Patch 写入、macro/mixed 扩展 | 已有证据，12 项测试通过 |

B3 的五类异常实际结果为：

`STALE_REPORT`、`SCHEMA_MISMATCH`、`ARTIFACT_TYPE_MISMATCH`、`ARTIFACT_HASH_MISMATCH`、`UPSTREAM_FAILED`。

每类异常均在 Patch 生成前拒绝，`patch_generated=false`，源项目和修复输出保持不变。B3 的 `summary.json`、`241880360-handoff.json` 和原始 case 证据均已位于 `reports/E11/B3/`。

## B4 验收执行

本地已执行：

```text
python -m unittest discover -s labs/e11e12 -p test_*.py -v
```

结果：`12 tests`，全部 `OK`，退出码 `0`。

完整镜像构建、E11-B 运行和 CI 已由 `.github/workflows/e11e12.yml` 在 Ubuntu 24.04 执行。运行 `42846917634` 成功，完整执行了合约测试、实验包准备、`e11-a`、`e11-b` 和 `e12`；原始输出已保存为 Artifact `e11e12-evidence-42846917634`。运行号、状态、Artifact 和摘要见同目录 `ci-run.json`。

E11-B 的 CI 证据已归档到 `e11-b/`：结果为 `SUCCEEDED`，第一轮 DRAFT 分类为 `MISSING_MAKE`，第二轮构建退出码为 `0`，镜像运行输出为 `1`；修复计划只增加 `config.h` 和 `extra.h`，动态重检后仅保留 `unused.h` 的 `REDUNDANT` 结论。

## B4 结论

B1、B2、B3 的交付边界和证据已完成核对；本分支补充了 B4 的集成验收报告、E11-B CI 结果和个人报告。B4 验收结论为 `PASS`，由组长审核后合并回 `e11-e12-integration`，再按组内流程决定是否合并到 `main`。

## 证据索引

- `reports/E11/B1/README.md`、`draft.json`、`draft-build/`
- `reports/E11/B2/README.md`、`241880179-handoff.json`、`candidate.patch`、`repair-plan.json`、`validation/`
- `reports/E11/B3/README.md`、`summary.json`、`241880360-handoff.json`、五类异常 case 目录
- `reports/E11/B4/acceptance.json`
- `reports/E11/B4/ci-run.json`
- `docs/students/241880610/e11-b4/个人报告.md`

