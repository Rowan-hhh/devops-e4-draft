# E15 B1 样例运行与故障恢复交接

## 任务范围

B1 负责启动本组微服务样例，核对 API、Worker、Prometheus、Grafana 的健康状态，完成正常任务、下游停止失败和恢复重跑，并把命令输出、状态响应、指标和日志交给 B2。

## 证据来源

本交接使用实验包中已经保存的 Linux/Docker 运行证据，原始运行时间为 `2026-11-19T06:37Z` 至 `2026-11-19T06:40Z`。证据已复制到 `reports/E15/B1/evidence/`，没有把 `.env` 或 Grafana 密码提交到仓库。

Compose 文件 SHA-256：

```text
dc5930e651bedb015d66bc49ffe1cc3bb86b29404a4a3b578c7d00907cf39f29
```

服务拓扑为 `api -> worker`，并由 Prometheus 抓取业务指标、Grafana 展示面板。正常任务的报告确认 `main.o` 缺少 `config.h`、声明冗余 `unused.h`。

## B1 运行结果

| 场景 | job_id | trace_id | 结果 | 错误码 | attempts |
|---|---|---|---|---|---:|
| 正常 | `job-18422aaf5a294d698665816fa4ef8d80` | `trace-0fe4af3fdf164823a4cffe0baa7a25dd` | `SUCCEEDED` | 无 | 1 |
| 下游停止 | `job-06cdfb90f12f42159644247ebb7d692f` | `trace-3a4fad57da2943fe9a71a02eb0ffd783` | `FAILED` | `DOWNSTREAM_UNAVAILABLE` | 3 |
| 恢复重跑 | `job-887bd102cae14981968821de52b17e50` | `trace-ac0427fbb10a4d95ad2614cc79c9fa4c` | `SUCCEEDED` | 无 | 1 |
| 超时补充 | `job-451f615089714cdcbbb0a70ecb978aea` | `trace-7e7ed873a33d49c8a1ae49bfcae7261c` | `TIMED_OUT` | `DOWNSTREAM_TIMEOUT` | 3 |

正常和恢复任务的报告 SHA-256 均为：

```text
f977fd00c840276f44eef7027a10ebef5ddeca60d4ba5bdd191ecdb89e148dc2
```

`services.log` 中保留了同一 `job_id`/`trace_id` 在 API 与 Worker 两侧的调用、失败、重试和结束事件；指标文件保留了任务计数和耗时结果。停止下游后的失败任务没有成功 artifact，恢复后新幂等键重新成功。

## 交接给 B2

- Compose 配置：`evidence/compose.yaml`
- 正常、失败、恢复和超时的 `status.json`、`check.json`、`metrics.txt`
- 正常和恢复的 `report.json`
- 完整服务日志：`evidence/services.log`
- 机器可读交接：`evidence/handoff.json`

## 边界说明

本交接保留的是实验包中已完成的真实运行证据，不重复覆盖原始 `work/`。当前 Windows 本机 Docker daemon 未启动，因此没有声称在本次整理时重新部署；若教师要求当日服务器复跑，应在服务器新建 evidence 目录后重新执行样例并替换交接摘要。`.env` 中的 Grafana 密码未进入交接或 Git。
