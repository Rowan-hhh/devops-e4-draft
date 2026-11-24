# E14 B2 四服务部署交接

本目录保存 E14 B2 的 Compose 配置、渲染结果、教学镜像身份、四服务健康状态、端口、Docker socket 边界和角色日志摘要。正式交接必须使用 `handoff.json` 中的 SHA-256；不得用 `latest` 或只写镜像 tag。

候选集成提交：`ff92071368bbd40083e3014dd09adc40a5c24dbb`。该值来自 E14 候选合并后的 main post-merge CI，镜像实际构建来源提交也为该 SHA。

需要交给 E14 B1 的文件：

- `evidence/handoff.json`
- `evidence/compose.yaml` 及 `evidence/compose-config.json`
- `evidence/image-inspect.json`
- `evidence/e2e-smoke-result.json`
- `evidence/health.json`
- `evidence/mounts-buildchecker.json`、`evidence/mounts-echecker.json`、`evidence/mounts-draft.json`、`evidence/mounts-mdfixer.json`
- `evidence/logs/` 下四份角色日志

本次刷新交付来源于 GitHub Actions 的真实 Linux/Docker post-merge 四服务作业：
运行地址为 `https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/44999746034`，四服务作业地址为 `https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/44999746034/job/137138443436`，证据 Artifact ID 为 `14745551416`。四服务健康后执行的固定样例 smoke run 五阶段均成功，`job_id=job-814f77a335124944a787f1e925f6afa7`，`trace_id=trace-5940632b2b17409d9477bbdaa306a0cc`，结果原始字节已纳入 `evidence/e2e-smoke-result.json`，`handoff.json` 中的 `e2e.result_path` 相对于 evidence 根目录，状态为 `SUCCEEDED`，退出码为 `0`。

镜像使用显式 tag `course-e11e12:241880610`，image ID 为 `sha256:5237c2af3c87ae7076f1801df1cf720bfecd7cdb29cf0041039f515cc4970e97`。本次 CI 未向镜像仓库推送，因此没有 RepoDigest；原因是 CI 仅在本地构建教学镜像，未执行 registry push，故以不可变 image ID 和 `evidence/image-inspect.json` 为权威身份依据。

当前证据是本次 post-merge CI 环境的实际 Compose 部署，所有文件的 bytes 和 SHA-256 已记录在 `evidence/handoff.json`。本交接不把旧的 E13 基线 `77da...` 当作候选身份；B1 可直接运行 `verify-service-handoff` 校验本次 `ff920...` 交接。

`handoff.json` 只有在四项服务均为 `healthy`、四份日志存在且 SHA 已记录、并确认 Docker socket 仅挂载到 DRAFT 后，才能标记为 `SUCCEEDED`。固定样例的五阶段运行由 E14 B1 在收到本交接后继续完成；本 B2 交接不把服务健康误写成 E2E 通过。
