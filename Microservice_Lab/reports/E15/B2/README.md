# E15 B2 本组项目接入与监控核对

## 来源与运行边界

B1 交接来自 `e15-xzt-b1`，已审计导入本分支；导入提交为
`f31d32733bee4f23aeae3a41cf8c9e995dfe4ba9`。B1 原始交接文件未改动，
SHA-256 为 `3535c69e78255f0f76ba975d001784c38185647d69e7bc4c06520b7349db5bbd`。
本报告以下运行是 B2 在服务器隔离 worktree 中新做的验证，不把 B1 归档运行当作本次复跑。

## 本组真实项目任务

E12 API 对真实仓库提交执行任务，基线
`0b62c79a6adb4cd913a814068074575afdbbd18b`，目标
`745ecf2621c8221b97bf0a5435ace50150ef57d4`。
任务 `job-0efa607b21d945d3b76c7fe63aed71fe`，追踪号
`trace-bb3eda8a38dc453097d2781526d1ca1b`，最终 `SUCCEEDED`。
`draft → full-check → incremental-check → repair → recheck` 五阶段完成；
验证前发现 `helper.o` 缺少 `output_format.h`，修复后 findings 为空。
请求、候选 Dockerfile、客户端阶段文件及结果位于 `evidence/real-project/`。
服务端与客户端下载的 `result.json` 字节一致，SHA-256 为
`309f06f4a7d425563050017794922071c913a9ff8b0a232f05924032536fa535`。

第一次尝试因服务端缺少 `buildchecker` 模块而以 `WORKER_FAILED` 结束；
这是部署环境问题，不是业务下游故障。保留原终态文件，
修正 API 运行环境后用新任务成功完成；没有覆盖或伪装第一次结果。

## 微服务样例、指标与截图

隔离 Compose 项目的 API、Worker、Prometheus、Grafana 已启动；
Prometheus 的 `lab-api`、`lab-worker` 目标均为 UP。
B2 新提交的样例任务 `job-1fb88159b49145a2a23ad3d1035dfa32`，
追踪号 `trace-b24b5b1528c14f6d855d30379b9ba0de`，`SUCCEEDED`，
`attempts=1`。API 与 Worker 日志可按相同任务号及追踪号关联。
Prometheus 抓取后的 `lab_jobs_total{status="SUCCEEDED"}` 为 1。
Grafana API 确认数据源、`microservice-lab` 面板及三条查询；
面板对应历史时段的 Prometheus 查询结果保存在 `evidence/monitoring/dashboard-queries/`。

- [截图 1：两个 Prometheus 目标均 UP](evidence/screenshots/1.png)
- [截图 2：样例成功任务计数为 1](evidence/screenshots/2.png)

截图是 Prometheus 页面；未获得 Grafana 页面截图。Grafana 的核验依据是
`evidence/monitoring/grafana-api/` 的 API 响应及面板查询结果。

## 交给 B3 的边界

上述监控指标与截图属于 **Microservice_Lab 样例**；真实 E12 项目使用
独立 API 完成五阶段任务，不能声称它的任务计数进入了样例面板。
B3 应在本组实验环境验证下游停止、失败终态与恢复重跑，
用新任务号和追踪号记录时间、日志与指标；不要把本次环境导入错误
当作下游故障证据。结构化摘要见 `evidence/handoff.json`。
未提交 `.env`、Grafana 密码或镜像传输 tar 包。
