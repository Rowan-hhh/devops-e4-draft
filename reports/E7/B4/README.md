# E7 B4 最终验收记录

## 验收对象

- 仓库：Rowan-hhh/devops-e4-draft
- PR：[#1](https://github.com/Rowan-hhh/devops-e4-draft/pull/1)
- 分支：`e7-yironghui-b4`
- B3 基线：`f4de26b3abe0dea5575f4ecd9c238d82ee1176e5`

## B3 已交付结果

- 服务测试：`17 passed`
- 五场景 gate：`passed=true`，总退出码 `0`
- gate 结束后残留容器：`0`
- timeout 场景分类：`TIMED_OUT`，验证退出码 `124`
- timeout 容器清理：`removed=true`

## CI 与分支规则

- Workflow：`.github/workflows/e7-b4-gate.yml`，名称 `E7 B4 CI`
- Required check：`E7 B4 Gate`
- Workflow 提交：`ad19226cc19f657cd87dd01011b0fdbefec843c7`
- main 分支规则集：`main-e7-gate`，状态 `Active`，目标 `Default branch`
- 规则要求 PR 后合并、状态检查通过且分支与 base 保持最新；required status check 为 `E7 B4 Gate`
- Required approvals：`0`
- 限制删除、禁止 force push；bypass list 为空

## 三阶段 CI 证据

| 阶段 | 提交与运行 | 结果 | Artifact 与 PR 状态 |
|---|---|---|---|
| 初始成功 | Run `40347473764`：[Actions](https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/40347473764) | `SUCCESS` | `e7-b4-40347473764-1`，84.6 KB |
| 故意失败 | `741d0e825b4bd7ffb07e20fbf767ba18f3ce944b`（`test(E7/B4): inject intentional CI failure`）；Run `40351314879`：[Actions](https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/40351314879) | `FAILURE`，退出码 `1` | `e7-b4-40351314879-1`，9.87 KB；PR 显示 `E7 B4 Gate` 为 Required 且失败，`Merge pull request` 按钮禁用 |
| 同一 PR 修复 | `a46404891b0abda148958185c8fa1000426bf7e2`（`test(E7/B4): restore passing CI gate`）；Run `40352623742`：[Actions](https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/40352623742) | `SUCCESS`；总时长 `1m 1s`，gate job `57s` | `e7-b4-40352623742-1`，84.6 KB；PR 显示 `All checks have passed`、`No conflicts with base branch`，合并按钮恢复可用 |

## 验收结论

已验证 required check 失败时阻止合并，并验证在同一个 PR 修复后检查恢复通过。故意失败测试已从最终树删除。当前状态为 **`ACCEPTED_PENDING_FINAL_REPORT_CI_AND_MERGE`**；PR 尚未合并，本记录不包含 merge commit。
