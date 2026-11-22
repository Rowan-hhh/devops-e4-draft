# E14 B2 四服务部署交接

本目录保存 E14 B2 的 Compose 配置、渲染结果、教学镜像身份、四服务健康状态、端口、Docker socket 边界和角色日志摘要。正式交接必须使用 `handoff.json` 中的 SHA-256；不得用 `latest` 或只写镜像 tag。

候选集成提交：`77da560719fe7835c227a289b6bc99295fa5abcc`。该值来自 E13 门禁通过后的最终合并提交。

需要交给 E14 B1 的文件：

- `handoff.json`
- `compose.yaml` 及 `compose-config.json`
- `image-inspect.json`
- `health.json`
- `mounts-buildchecker.json`、`mounts-echecker.json`、`mounts-draft.json`、`mounts-mdfixer.json`
- `logs/` 下四份角色日志

`handoff.json` 只有在四项服务均为 `healthy`、四份日志存在且 SHA 已记录、并确认 Docker socket 仅挂载到 DRAFT 后，才能标记为 `SUCCEEDED`。固定样例的五阶段运行由 E14 B1 在收到本交接后继续完成；本 B2 交接不把服务健康误写成 E2E 通过。
