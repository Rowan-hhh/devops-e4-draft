# E13 B1 AI 使用记录

姓名/学号：史美一 / 241880179

工具与日期：Codex，2026-11-17 至 2026-11-18。

## 使用范围

AI 协助阅读 E13 PDF 和操作手册、核对 A 组交接字段、建立个人分支、导入课程官方脚本、补充 fixed-md 字节哈希校验与测试、执行服务器命令、整理 C1/C2、公共准备和 H1 证据，并形成报告初稿。

## 结果来源与边界

C1/C2、54 项公共契约测试、baseline 和 H1 五阶段结果均来自 GitHub Actions 或课程服务器上的实际程序运行。AI 没有生成伪造的成功 JSON，没有用公网 jsmn 替代教师项目，也没有把教师 ZIP、上游源码、服务器密码或真实密钥提交到公开仓库。

baseline 首次因 Debian 官方源下载超时而失败，报告保留该失败及无残留检查；后续只在隔离副本切换镜像源并使用新目录复跑。最终结论依据服务器生成的 job/trace、退出码、Patch、validation、recheck 和 SHA-256。

## 人工复核结果

本人已核对 `reports/E13/B1/README.md`、`server-run/241880179-handoff.json`、H1 Patch/validation/recheck、C2 两项拒绝结果和本记录，确认文字与原始证据一致。
