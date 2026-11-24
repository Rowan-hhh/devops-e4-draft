# E12 B4：五阶段最终验收与小组交付

- 负责人：史美一（`241880179`）
- 分支：`student/241880179/e12-b4`
- 集成输入提交：`092d00e89a0857652326530703640b481da7222f`
- B2 PR：[#23](https://github.com/Rowan-hhh/devops-e4-draft/pull/23)，已先合并
- B3 PR：[#24](https://github.com/Rowan-hhh/devops-e4-draft/pull/24)，已后合并

## A/B 真实交接

B2 消费的 A 组 `incremental-check.json` SHA-256 为
`66e3bfb2c39d4c8b0913d4b5afb269d284cb1369e05d68b4fd889170e1e38a83`，与 A 组截图和仓库归档一致。

- A 组 job：`job-701e024edd564902a625716aa9547cf7`
- A 组 trace：`trace-be8e398fc0564ebcb177991840937797`
- base：`0b62c79a6adb4cd913a814068074575afdbbd18b`
- target：`745ecf2621c8221b97bf0a5435ace50150ef57d4`
- 发现：`helper.o → output_format.h (MISSING)`

## B4 最终运行

GitHub Actions 在最新集成树上重新执行真实项目五阶段，而不是只复用 B3 的成功文字：

1. `draft`：第一轮 `MISSING_MAKE`，第二轮构建成功，禁网运行输出 `1`；
2. `full-check`：基线全量 BuildChecker 成功；
3. `incremental-check`：目标增量检测成功；
4. `repair`：为 `helper.o` 增加 `output_format.h`；
5. `recheck`：Patch 五项验证全部通过，最终无 `MISSING`。

- 最终 job：`job-a8c716a97754454d990c997cc9929d4b`
- 最终 trace：`trace-f535cebe0ae94d57ba375b66d43f5f33`
- 状态：`SUCCEEDED`
- 产物数量：174
- `accepted=true`
- 最终 findings：0

## 四人贡献

| 成员 | 学号 | E12 贡献 | 验收结果 |
|---|---|---|---|
| B1 | 241880360 | 维护项目、base/target、候选 Dockerfile、DRAFT 两轮构建 | SUCCEEDED |
| B2 | 241880610 | 消费 A 组真实增量报告、生成 Patch、验证与重检 | SUCCEEDED |
| B3 | 241880300 | API 提交/轮询/下载、哈希、幂等与 409 契约 | SUCCEEDED |
| B4 | 241880179 | 合并顺序、五阶段最终验收、CI、汇总与最终 PR | SUCCEEDED |

## CI 与归档

- E11–E12 run：[43607400605](https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/43607400605)，success
- E8–E10 回归 run：[43607400625](https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/43607400625)，success
- Artifact：`e11e12-evidence-43607400605`
- Artifact ID：`14118731280`
- Artifact digest：`sha256:19ea6e475a0d969305eae1b1f69a8ab9ac3adb22c5e1d6d9c9f634c6ff93fdac`

核心结构化结论见 `result.json`，五阶段原始总清单见 `five-stage-result.json`，五份阶段报告见 `stages/`，最终验证和 findings 分别见 `validation/` 与 `final-full/`。
