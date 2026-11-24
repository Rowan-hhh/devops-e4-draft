# E14 B3：A/B 真实项目五阶段验收

## 结论

E14 B3 已在课程服务器的四服务 Compose 环境中，分别对 A 组 A05 真实交换项目和 B 组维护项目执行
`draft → full-check → incremental-check → repair → recheck`。两轮均为 `SUCCEEDED`，补丁验证接受，最终 `MISSING=0`。

- 候选代码提交：`ff92071368bbd40083e3014dd09adc40a5c24dbb`
- 本次工具基线：`b1f665922b189db303a63be53e21cf614682dfee`
- 教学镜像：`course-e11e12:241880179`
- 镜像 ID：`sha256:b7b3426a362ad9fbbb06d22aa4c82ba19f2b6f1b36bd401ff2e70f90db02f863`
- Compose 项目：`e14-241880179-b3`
- 四服务运行时均为 `healthy`，任务结束后只关闭本 Compose 项目，剩余容器数为 0。

## A 组 A05 项目

- base：`6b9deff53f8fcf6183204850ac6a9dddb22f1189`
- target：`90646db8b8ad932da1a959d152942f987aaffff2`
- job：`job-383755ea09044810bf772ba007c61188`
- trace：`trace-85eefd1e95674d5da98b275ba270977f`
- 产物数：181
- 候选 Patch SHA-256：`0030f288c5f8b50afed0df84334185a2d1276b4bbbdc37f39314ee5c04bef9db`
- validation：`accepted=true`
- recheck commit：`90646db8b8ad932da1a959d152942f987aaffff2`
- 最终 `MISSING=0`
- `result.json` SHA-256：`0513e77e302cfcf2415c28133c5999133228671c3a419e1724ad89d78348440d`

## B 组维护项目

- base：`0b62c79a6adb4cd913a814068074575afdbbd18b`
- target：`745ecf2621c8221b97bf0a5435ace50150ef57d4`
- job：`job-579414c3149341b18f5c3cd3137f2cb6`
- trace：`trace-bc3f60d6ec8f4f10b4f0263ac811ddd11`
- 产物数：180
- 候选 Patch SHA-256：`a7a3be54d5ba81594acd628725f17aca2b4ce0d1a5aed556d454bb321eb5142a`
- validation：`accepted=true`
- recheck commit：`745ecf2621c8221b97bf0a5435ace50150ef57d4`
- 最终 `MISSING=0`
- `result.json` SHA-256：`11ff0b4d1882b3ad25b759c60de01767340ed8a4021c0978c12b197994fa1ec3`

## 校验与边界

- E11–E12 回归：54 项全部通过。
- 两轮的五个阶段均与各自 `result.json` 共享同一 job/trace，阶段状态均为 `SUCCEEDED`。
- A/B 两轮所有可读产物的 SHA-256 与 `result.json` 清单一致。
- 运行后两个原始 Git 项目工作区仍为干净状态。
- 扫描 343 个文本证据文件，结果 `hits=0`、`errors=0`。
- B 项目前两次调用在任务启动前因旧请求路径不符合 E14 `/course/data` 合约被拒绝；失败日志保留，之后使用新输出目录重跑成功。

## 证据目录

- A05：`server-run/e14-b3-a05/`
- B 项目：`server-run/e14-b3-b-project-retry2/`
- 四服务日志：`server-run/e14-b3-service-logs/`
- Compose、镜像和输入哈希：`server-run/e14-b3-metadata/`
- 日志扫描：`server-run/e14-b3-runtime-scan.log`
- 结构化交接：`241880179-handoff.json`

服务器原始工作目录：`/root/devops-students/241880179/e14-b3`。导出归档 SHA-256 为
`cfd5888b364638e8a52b9f4761733fd4a35fa5cfc8676c9d3933f76c70c9c0c3`。
