# E14 B1：正式固定样例验收

## 结论

E14 B1 正式结果为 **PASS**。锁定候选代码提交为
`ff92071368bbd40083e3014dd09adc40a5c24dbb`；正式工具基线为
`588957ad6373e45fa166ed5a58c546bea018669d`。两者身份不同：
前者是 E14 候选代码，后者包含后续交接验证、CI 可移植性和 CLI 修复。

固定样例、单容器正式运行、B2 部署交接核验和四服务固定样例均已完成。
证据归档时间：`2026-11-23T05:20:24Z`。

## 固定样例

- base：`4d6815a591fe87ea7b511c8b3e9f021d413e4415`
- target：`eac8fcd24bc182be27f07ee50544fccc9a1e6826`
- request SHA-256：`422f4bdd9d9e1eeded9d03584a3219185c429fee484dbdcd90e0e5bcdad77c1c`
- candidate SHA-256：`c2f7a9f70caf44bbf4852a1c61e262203de9f28cd6fbe3aa2dec5adf6d34c6da`
- fixed report SHA-256：`98f33161543830077ca311ddface7f7e2b5d4bb94fc470ed595c8843ba9b305c`
- Git bundle 已完成 verify、恢复、祖先关系和 tree/blob 核验。

## 单容器正式运行

- 状态：`VERIFIED`
- job：`job-c2ab330095604b6d952029bf5814d393`
- trace：`trace-0fb577d273bd4c1e99c9955e0f9ce416`
- 阶段：`draft → full-check → incremental-check → repair → recheck`
- artifact：`156`
- 运行前后原始输入仓库边界状态一致。
- `sealed-inputs/` 与 `sealed-run/` 可用于离线复核。

首次正式运行因 Debian 网络下载超过 600 秒失败，失败 job、trace、封存控制证据和诊断均保留。
恢复时仅预热完全相同的候选 Dockerfile 与固定样例 target，没有修改请求、候选字节、
源历史或期望输出；恢复运行使用独立 job/trace 并通过离线验证。

## 四服务正式运行

- 状态：`VERIFIED`
- job：`job-63b04038ab0d4f4dad41338d6a45cc2a`
- trace：`trace-97c74bcea0c247b899798f83ad59e162`
- 阶段：`draft → full-check → incremental-check → repair → recheck`
- artifact：`162`
- BuildChecker、EChecker、DRAFT、MDFixer 均为 `running/healthy`
- 端口仅绑定 `127.0.0.1:18081–18084`
- Docker socket 仅挂载至 DRAFT
- 四服务结束后本 Compose project 无剩余容器
- 服务日志与运行证据扫描退出码均为 0

四服务归档保留 Compose、渲染配置、镜像 inspect、健康状态、挂载、
服务日志、结果、阶段和输出产物；排除了 mutable run 中的嵌套 Git 工作副本。
原始完整工作证据由 verification 中的前后 SHA-256 manifest 绑定。

## B2 交接

B2 handoff 已由 B1 验证器核验，状态为 `HANDOFF_VERIFIED`，其
`candidate_commit` 与锁定候选
`ff92071368bbd40083e3014dd09adc40a5c24dbb` 一致。

## 证据边界

运行包装器对原始输入仓库采集运行前后边界状态；该结论证明两个边界一致，
不声称能够观察运行期间的每一个瞬时状态。正式服务器运行时没有相关并发任务，
候选输入由专属、干净工作目录控制，运行后立即重新核对字节哈希。

归档不包含教师 ZIP、原始 `data/` 或嵌套 `.git` 工作副本。
提交证据的文件大小和 SHA-256 统一记录于 `evidence/manifest.json`。

## CI

工具基线 `588957ad6373e45fa166ed5a58c546bea018669d` 的以下 CI 已通过：

- E13–E14 integration gate：45100922685
- E11–E12 integration：45100922679
- E8–E10 teaching validation：45100922673
- E7 B4 CI：45100922678

正式归档提交的 `archive_ci` 当前为 `NOT_RUN`；必须由本分支 PR CI 和合并后
main CI 验证后再完成最终交接。

## 交接文件

- `identity.json`
- `handoff.json`
- `evidence/manifest.json`
- `evidence/single-container/`
- `evidence/single-container-failed/`
- `evidence/four-services/`
- `evidence/b2-handoff-verification/`
- `evidence/recovery.json`

下一接收角色：E14 B4。
