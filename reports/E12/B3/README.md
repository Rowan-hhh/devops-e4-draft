# E12 B3：A/B API 联调与契约检查

- 负责人：周逸涵（`241880300`）
- 分支：`e12-zyh-b3`
- 目标分支：`e11-e12-integration`
- 上游 B2：`e12-xzt-b2`，提交 `ad230ba0116e8931d2943886f5ee159fbf53ddc7`
- B2 目标提交：`745ecf2621c8221b97bf0a5435ace50150ef57d4`
- B2 真实报告 SHA-256：`66e3bfb2c39d4c8b0913d4b5afb269d284cb1369e05d68b4fd889170e1e38a83`

## 联调结果

本次 CI 使用 B1 bundle 恢复真实项目，并通过现有 API 服务提交 E12 请求。请求、轮询、产物清单、下载响应和服务日志均保存在 `run/`：

- `job_id`：`job-171994714e734e78a5cdc29346d12a92`
- `trace_id`：`trace-41596e50faf94fe59b74a28ef84a5648`
- 最终状态：`SUCCEEDED`
- 产物数量：174
- 请求输入 SHA-256：`7023862e7c6578f45c16db3f48e4d809cc26ef6f5294cbcac32e0bde1988aeed`

下载的 `candidate.patch`、`repair-plan.json`、`validation/validation.json` 和 `recheck.json` 均核对了 API 响应头 `X-Content-SHA256`、产物清单 SHA-256 和本地下载 SHA-256，四项全部一致。

## 契约检查

- 首次提交：HTTP 202，返回完整 `job_id`。
- 轮询：最终返回 `SUCCEEDED` 和完整 `trace_id`。
- 相同幂等键、相同输入重复提交：HTTP 202，复用同一个 `job_id`。
- 相同幂等键修改 `target` 后提交：HTTP 409，错误为 `IDEMPOTENCY_CONFLICT`。
- API 访问方式：服务器 loopback；SSH 转发格式为：
  `ssh -N -L 18081:127.0.0.1:8080 <account>@<api-server>`

## CI 证据

- CI：[run 43572200027](https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/43572200027)
- CI 提交：`b54f959a5e526fc9ef10209bd89a79fb2df601ee`
- Artifact：`e11e12-evidence-43572200027`
- Artifact ID：`14104239175`
- Artifact digest：`sha256:100998525a9e19510fe01b20cdf9c7b0389f7e1899df1cbe80616a82b582c1d4`

具体交接数据见 [`run/handoff.json`](run/handoff.json)，客户端实现见 [`scripts/e12_b3_api.py`](../../../scripts/e12_b3_api.py)。
