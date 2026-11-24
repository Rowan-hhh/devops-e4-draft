# E13 B4 最终门禁汇总

负责人：谢真婷（241880610）  
分支：`e13-xzt-b4`  
基线：`84b0e1df446265471e6b0c41386193785f75dc8b`（E13 B3 已合入 `main`）

## 结论

E13 B4 已完成 C6 假密钥扫描、C8 幂等冲突测试、C1–C8 结果汇总、教师项目归档核对和 CI/Issue/PR 检查。A 组已确认签收 C4/C7 结果，因此 E13 门禁可以判定为 **PASS**；下一步进入 E14，不再需要等待 A 组补交实验结果。

## C1–C8 汇总

| 门禁 | 来源 | 结果 | 关键证据 |
|---|---|---|---|
| C1 | E13 B1 | PASS | `reports/E13/B1/`；A/B 实际项目正常链路，最终 `MISSING=0` |
| C2 | E13 B1 | PASS | `STALE_REPORT`、`WRONG_TARGET` 均被拒绝，未启动修复 |
| C3 | E13 B2 | PASS | `ARTIFACT_HASH_MISMATCH`，未接受篡改报告、未启动修复 |
| C4 | E13 B3 | PASS | 超时后任务终止，源码未变、构建客户端/验证容器无残留 |
| C5 | E13 B2 | PASS | 无效 Patch 被拒绝并回滚，源码前后不变 |
| C6 | 本次 B4 | PASS | 假密钥命中退出码 1；清理后退出码 0；正式证据目录扫描 0 hits/0 errors |
| C7 | E13 B3 | PASS | 失败任务构建前失败且与正常任务隔离，正常任务成功 |
| C8 | 本次 B4 | PASS | 相同 key+请求返回同一 `job_id`；相同 key+变更 target 返回 409 `IDEMPOTENCY_CONFLICT` |

## 教师项目

H1 jsmn、H2 inih、H3 tiny-AES 均来自独立教师项目，不能替代 A/B 实际交换项目；三项均已有正式成功证据，最终缺失依赖为 0，源码保持不变。

## A/B 交接与 CI

- B3 交接提交：`84b0e1df446265471e6b0c41386193785f75dc8b`。
- A 组已确认签收 C4/C7 结果；签收范围不改变 B3 的原始证据。
- 已检查 B1、B2、B3 交接目录和 Issue/PR 记录；缺陷均有拒绝、回滚或隔离证据。
- B3 服务器回归：E13 42 tests、E13E14 5 tests、官方 E11/E12 容器 54 tests 全部通过；runtime scan 为 721 个文本文件、0 hits、0 errors、exit 0。
- B3 CI：E13 local contracts、E11–E12 integration、E8–E10 teaching validation 均 success；本分支另有 B4 contract test，见 `labs/e13/test_e13_b4.py`。

## 证据索引

- C6：`reports/E13/B4/c6/`
- C8：`reports/E13/B4/c8/`
- 结构化结果：`reports/E13/B4/result.json`
- 交接：`reports/E13/B4/handoff.json`
- 个人报告：`docs/students/241880610/e13-b4/个人报告.md`

