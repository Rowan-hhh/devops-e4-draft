# E15 B3 下游故障注入与恢复验证

## 输入与隔离边界

- 学号：`241880179`
- 姓名：史美一
- 上游分支：`e15-yrh-b2-real-project`
- 上游提交：`3eb5d2a886d5b82b8e00a82aca0193a001c98786`
- B2 真实 E12 正常任务：`job-0efa607b21d945d3b76c7fe63aed71fe`
- B2 样例正常任务：`job-1fb88159b49145a2a23ad3d1035dfa32`
- 本次 Compose 项目：`e15b3smy20261126`

本次在独立工作树和独立 Compose 项目中重新部署样例，使用独立端口，不停止
B2 的容器，也不改动真实 E12 四服务。Prometheus/Grafana 指标只属于
`Microservice_Lab` 样例，不用于证明真实 E12 项目进入了该面板。

## 故障注入

在 Worker 健康且 Prometheus 显示 `lab-worker up=1` 后，于
`2026-11-26T15:34:38+08:00` 停止本隔离项目的 `worker`。等待 Prometheus
显示 `up=0` 后，使用新幂等键提交样例任务。

|字段|结果|
|---|---|
|job_id|`job-3063e546ab6549619dbed4e5958be77e`|
|trace_id|`trace-2f76c0e7a8b842d6a5e91cc0fe049263`|
|终态|`FAILED`|
|错误码|`DOWNSTREAM_UNAVAILABLE`|
|attempts|`3`|
|duration_ms|`1011`|

故障状态文件没有成功 artifact。按 `job_id` 提取的日志包含 3 次
`worker_call`、3 次 `worker_error` 和 1 次 `job_finished`，最终日志中的
终态、错误码、重试次数与状态响应一致。

## 恢复重跑

启动同一隔离项目的 Worker，等待健康检查与 Prometheus 恢复为 `up=1`，
于 `2026-11-26T15:34:46+08:00` 使用新幂等键重新提交相同样例输入。

|字段|结果|
|---|---|
|job_id|`job-b5ee89f4b33b401c896ce2ee0b2ab22c`|
|trace_id|`trace-f42636ec1a29499ebf624e379dbd2bfb`|
|终态|`SUCCEEDED`|
|错误码|无|
|attempts|`1`|
|duration_ms|`3`|
|报告 SHA-256|`f977fd00c840276f44eef7027a10ebef5ddeca60d4ba5bdd191ecdb89e148dc2`|

下载后的 `report.json` SHA-256 与状态响应一致，内容仍为 `main.o` 缺少
`config.h`、冗余声明 `unused.h`。API 与 Worker 日志中可使用相同的
`job_id` 和 `trace_id` 关联恢复任务。

## 指标与仓库状态

本次保存的 Prometheus 响应显示 Worker 抓取状态按预期从 `1` 降为 `0`，
恢复后再回到 `1`。运行结束后 API、Worker、Prometheus、Grafana 均运行，
Worker 最终恢复为 healthy。故障注入前后没有修改应用源码、依赖集合或
Compose 文件；原始 Git 工作区保持干净。

## 证据目录

- 操作时间、Compose 状态、Prometheus 响应和筛选日志：
  `evidence/b3-failure-recovery-20261126T073437Z/`
- 故障任务请求、状态、指标和检查结果：
  `evidence/down-20261126T073442Z-771dee/`
- 恢复任务请求、状态、报告、指标和检查结果：
  `evidence/recovered-20261126T073446Z-dd4195/`
- 服务器原始任务证据归档：`evidence/server-evidence.tgz`
- 归档 SHA-256：
  `c6a2ae9ecfe599bdc3f8bc1d306a951e849405b85e9f65ce362355fa69fbd8ab`

## 交给 B4

B4 可直接按 `evidence/handoff.json` 核对本次两个新任务，并在最终验收中明确：

1. B2 的真实 E12 正常任务与本次样例故障恢复属于不同观测边界；
2. 本次失败来自实际停止 Worker，不是 B2 首次运行的模块路径配置错误；
3. 故障任务没有成功 artifact，恢复任务使用新幂等键并得到新的任务编号；
4. 最终 Worker 已恢复，原始仓库状态未改变。
