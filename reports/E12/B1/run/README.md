# E12 B1 服务器原始证据索引

本目录归档本人真实服务器执行结果。本次整理不重跑 Docker、不改写原始证据。
原始输出在整理前建立了 91 个文件的 SHA-256/大小快照，整理后逐项复核。
本 README 是后加索引，不属于那 91 个原始文件。

| 路径 | 内容 |
|---|---|
| success/ | 最终成功的 B1 请求、结果、DRAFT 两轮、镜像 inspect、程序输出、源状态和隔离源码副本 |
| timeout/ | 旧候选第二轮官方 Debian 源下载超时；TIMED_OUT、source_unchanged=true，保留实际日志 |
| metadata/ | 执行提交、环境、服务与候选镜像 inspect、46 项服务器测试、退出码及服务器原始哈希记录 |
| related-logs/ | Docker Hub 拉取失败、同 digest 镜像替代成功、前置身份拒绝及两次运行控制台记录 |
| transfer-sha256.txt | 传输 success/timeout/metadata/related-logs 四个 tar 包的 SHA-256；tar 包本身未提交 |

为避免外层 Git 将运行副本识别为 gitlink，传输时仅排除了每次运行的
`target-project/.git`；其余输出原样保留。服务器仍保存含该 Git 元数据的原始完整输出。
`draft-build/project` 本来就由程序排除 .git，不是传输时另行裁剪。
metadata 中原始哈希清单可能包含未传输的 .git 路径和服务器绝对路径，保持原样，
不把它们冒称为当前归档的完整清单。

transfer-sha256.txt 校验传输 tar 包，不直接校验解包后的逐个文件。
当前归档每个文件（含本索引、隐藏文件和各原始清单）均由上一级
archive-manifest.json 独立记录相对路径、SHA-256 和字节数；manifest 排除自身。
所有交接入口见上一级 handoff.json，不依赖访问服务器绝对路径。

成功运行标识为 work/e12-B1-241880360-20261111T070145Z，执行提交为
8cd9224f32f73594c1c921cd4553cedb3760b55f；最终状态 SUCCEEDED，
第一轮 MISSING_MAKE/1，第二轮 0，禁网运行输出为 1 加一个换行、退出码 0、stderr 为空。
旧候选超时标识为 work/e12-B1-241880360-20261111T062651Z，不与最终成功合并或覆盖。

success/draft-build/cleanup-stderr.log 保留了 No such container 原文：运行命令已经使用
--rm，结束后清理再次查找该容器时不存在；不将这条清理日志改写为空，也不影响已记录的程序退出码。
未收到 A 组真实报告；本目录没有 A 组检测、B2 最终 Patch、B3 API 或 B4 五阶段验收产物。
