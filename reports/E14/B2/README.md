# E14 B2 四服务部署交接

本目录保存 E14 B2 的 Compose 配置、渲染结果、教学镜像身份、四服务健康状态、端口、Docker socket 边界和角色日志摘要。正式交接必须使用 `handoff.json` 中的 SHA-256；不得用 `latest` 或只写镜像 tag。

候选集成提交：`77da560719fe7835c227a289b6bc99295fa5abcc`。该值来自 E13 门禁通过后的最终合并提交。

需要交给 E14 B1 的文件：

- `evidence/handoff.json`
- `evidence/compose.yaml` 及 `evidence/compose-config.json`
- `evidence/image-inspect.json`
- `evidence/health.json`
- `evidence/mounts-buildchecker.json`、`evidence/mounts-echecker.json`、`evidence/mounts-draft.json`、`evidence/mounts-mdfixer.json`
- `evidence/logs/` 下四份角色日志

本次交付来源于 GitHub Actions 的真实 Linux/Docker 四服务作业：
`https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/44994745296`，作业成功；证据 Artifact ID 为 `14743103309`。四服务健康后执行的固定样例 smoke run 也完成五阶段成功，`job_id=job-838b17b108174ed4b6ac446fd03840db`，证据结果见 `e2e-smoke-result.json`。B1 收到交接后仍应按 E14 B1 职责在最终候选上重新运行固定样例。

镜像使用显式 tag `course-e11e12:241880610`，image ID 为 `sha256:c2aa501672f77d3827a956071c4321fb698a5ec5bf8d43b6647e16a85021104e`。本次 CI 未向镜像仓库推送，因此没有 RepoDigest；image inspect 和不可变 image ID 已保留，不能把空 RepoDigest 写成成功推送。

当前证据是 CI 环境的实际 Compose 部署；本机 Windows Docker daemon 未运行，正确服务器的 SSH 初始密码也被拒绝，因此尚未声称完成服务器专属复跑。若课程要求必须使用服务器，应在服务器凭据恢复后用同一 Compose 和同一候选提交复跑，并替换/追加 `evidence/`，不能覆盖本次 CI 证据。

`handoff.json` 只有在四项服务均为 `healthy`、四份日志存在且 SHA 已记录、并确认 Docker socket 仅挂载到 DRAFT 后，才能标记为 `SUCCEEDED`。固定样例的五阶段运行由 E14 B1 在收到本交接后继续完成；本 B2 交接不把服务健康误写成 E2E 通过。
