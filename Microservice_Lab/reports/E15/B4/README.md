# E15 B4 真实 E12 项目集成与最终验收

## 身份与输入

- 负责人：周逸涵（`241880300`）
- 分支：`e15-zyh-b4-final-acceptance`
- 验收基线分支：`e15-yrh-b2-real-project`
- 基线提交：`d6a8a3a4cff85767135ab3f418e04bb2e345b969`（已包含 B1、B2 与合并后的 B3）
- E12 真实项目基线：`0b62c79a6adb4cd913a814068074575afdbbd18b`
- E12 真实项目目标：`745ecf2621c8221b97bf0a5435ace50150ef57d4`

本次 B4 在 B2 已交付的真实 E12 项目和候选 Dockerfile 上新建隔离运行目录，重新执行 `draft → full-check → incremental-check → repair → recheck`。原始项目 bundle、B2 交付证据和 B3 样例运行均未修改。

## B4 真实项目复跑

首次任务 `job-860723b112c546a1aad6d46df26907a4` 因 Worker 的 Python 模块路径缺少 `buildchecker` 而以 `WORKER_FAILED` 结束。原请求和失败状态保存在 `evidence/initial-module-path-failure/`。修正服务启动时的 `PYTHONPATH` 后，用新幂等键创建了独立重跑；未覆盖第一次失败。

| 项目 | 结果 |
|---|---|
| 最终任务 | `job-b859630a9e89447a9ff692f715fe3208` |
| trace | `trace-de52b2f8c6214a95bafc9aabf8ccba2b` |
| 终态 | `SUCCEEDED` |
| 阶段 | `draft`、`full-check`、`incremental-check`、`repair`、`recheck` 全部完成 |
| 项目输入 | base `0b62c79a6adb4cd913a814068074575afdbbd18b`；target `745ecf2621c8221b97bf0a5435ace50150ef57d4` |
| DRAFT 候选 | SHA-256 `c7b2ba5babf97c0c413583d908ab372b224a6351f127124b068f1607aefc44af`，与 B2 交付一致 |
| 隔离构建 | 第 1 轮因候选 Dockerfile 缺少 Make 而失败；第 2 轮构建成功，镜像 `sha256:b6b3f4300dc42f3eaf5017e4d0ec0bb765067710614f70cf9d846fde341ec122` |
| 隔离运行 | 无网络、限制 CPU/内存/PID；实际输出 `1`，符合预期 |
| 增量检查 | 发现 `helper.o` 缺少 `output_format.h` |
| 修复 | `helper.o` 增加直接依赖 `output_format.h`；Patch SHA-256 `a7a3be54d5ba81594acd628725f17aca2b4ce0d1a5aed556d454bb321eb5142a` |
| 接受验证 | `accepted=true`；Patch 应用、构建、测试、头文件变化和无缺失五项均为 true |
| 最终复验 | `findings_after=[]`，`MISSING=0` |

服务端结果清单记录 174 项产物。已逐项比对本地保存的五阶段 JSON 与 `result.json` 中的 SHA-256，五项全部一致。`result.json` SHA-256 为 `96c2767d7f83a69a5a541e1184836a9d256de3a1e4358032502600516ff6c9aa`；Patch 计划 SHA-256 为 `ca830d7c2fc9db590984afe8b96f814b7f080d8b0066fc358c619f9bc2d4ac2a`；最终 findings SHA-256 为 `ab7bbb5ec4107c4a305898c1ccfcf785cf0e2e6e6799378b78443a66d88bbf51`。

验收验证文件还记录 `source_unchanged=false`、`rollback=false`。本次 B4 范围验证候选修复的接受与复验，没有执行拒绝/回滚场景；因此不把这两个字段表述成回滚通过。原始 bundle 和仓库交付文件保持未改动，运行产物均保存在新建的隔离目录。

## B1—B3 交接核对与观测边界

- **B1 样例**：交接状态为 `PASS_WITH_ARCHIVED_RUN`。其正常、下游停止、恢复和超时证据来自已归档运行；本报告保留这一来源说明，不声称它是本次新复跑。原始记录在 `../B1/README.md` 与 `../B1/evidence/`。
- **B2 本组真实项目**：五阶段真实 E12 任务 `job-0efa607b21d945d3b76c7fe63aed71fe` 成功，报告 SHA 与 handoff 一致。B2 的样例 Prometheus/Grafana 指标只描述 `Microservice_Lab` 样例，不代表真实 E12 项目进入监控面板。记录在 `../B2/README.md` 与 `../B2/evidence/`。
- **B3 样例故障恢复**：隔离 Worker 故障使 Prometheus `up` 从 `1 → 0`，任务 `job-3063e546ab6549619dbed4e5958be77e` 以 `FAILED / DOWNSTREAM_UNAVAILABLE / attempts=3` 结束；恢复后新任务 `job-b5ee89f4b33b401c896ce2ee0b2ab22c` 成功，`attempts=1`。这组指标仍只属于样例。记录在 `../B3/README.md` 与 `../B3/evidence/`。
- **B4 真实 E12**：独立于样例监控，使用固定真实项目 base/target SHA 完成五阶段任务，Patch 接受且最终 `MISSING=0`。

## 演示顺序与证据索引

1. 展示 `evidence/real-project-input.json`，核对真实项目 base/target SHA 和 B2 候选输入。
2. 展示 `evidence/real-project-run/request.json`、`submitted.json`、`status.json` 与 `result.json`，确认任务、trace、终态和五阶段产物。
3. 展示 `draft-build/result.json`、两轮构建日志及 `image-inspect.json`，说明第一次候选构建失败后第二轮成功，并查看隔离程序输出。
4. 展示 `incremental-check.json`、`repair-plan.json` 和 `candidate.patch`，核对唯一缺失依赖及修复内容。
5. 展示 `validation/validation.json`、`validation/recheck.json`、`check.json` 与 `final-full/findings.json`，核对接受结果和最终零缺失。
6. 如需说明环境排错，展示 `evidence/initial-module-path-failure/`，再对照成功重跑请求；两个任务号不同，失败记录未被覆盖。
7. 最后按本报告的观测边界展示 B1—B3 交接：样例运行/监控与真实 E12 项目运行分别陈述。

完整本地证据位于 `evidence/real-project-run/`。结构化交接见 `handoff.json`。未提交服务器凭据、`.env` 或容器镜像 tar 包。
