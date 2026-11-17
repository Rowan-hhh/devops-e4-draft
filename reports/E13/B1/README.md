# E13 B1：C1 正常链路、C2 身份拒绝与 jsmn 独立运行

负责人：史美一（241880179）  
分支：`student/241880179/e13-b1`

## 固定的 A→B 输入

- A 组仓库：`ZaneOw0/devops-e7-buildchecker`
- A 组验收提交：`d9e3cccadcfc94c46b1bf9dd54d92dd47c75cce5`（PR #14）
- A 组交接文档：`docs/e11-e12/A05-AB交接与组级验收.md` §2.1
- 上游 job：`job-701e024edd564902a625716aa9547cf7`
- 上游 trace：`trace-be8e398fc0564ebcb177991840937797`
- base：`0b62c79a6adb4cd913a814068074575afdbbd18b`
- target：`745ecf2621c8221b97bf0a5435ace50150ef57d4`
- 原始报告 SHA-256：`66e3bfb2c39d4c8b0913d4b5afb269d284cb1369e05d68b4fd889170e1e38a83`
- B 组真实项目 bundle SHA-256：`0a74f580219b55ab97119cdfa81f730f23fd0d5cbfbf2f986e4791110f3ce608`

`a-input/incremental-check.json` 保留 A 组实际交付的原始字节；没有使用重新排版后的副本代替。

## 门禁设计

- C1：校验 A 组固定提交、交接文档、报告身份和项目/报告哈希；在全新副本中执行 Patch、构建、测试、头文件变化检查与重检，要求最终 `MISSING=0`。
- C2 旧报告：将报告的 envelope commit 与 data commit 改为 base，只在隔离目录消费，必须以 `STALE_REPORT` 拒绝且不得开始修复。
- C2 错误目标：用真实报告请求错误 target，必须以 `WRONG_TARGET` 拒绝且不得开始修复。
- 三项原始输入在测试前后重新计算 SHA-256，任何变化都会使门禁失败。

实现位于 `labs/e13/e13_b1.py`，单元测试位于 `labs/e13/test_e13_b1.py`，CI 位于 `.github/workflows/e13-b1.yml`。服务器复跑结果为：C1 `SUCCEEDED`、最终 `MISSING=0`；旧报告以 `STALE_REPORT` 拒绝；错误目标以 `WRONG_TARGET` 拒绝；两个 C2 场景均为 `repair_started=false`。

## 教师 H1-jsmn 项目

输入使用 2026-11-16 学生发放包内的原始 `e13-upstream-student.zip`，没有使用公网项目代替。教师包仅在课程服务器的隔离工作目录使用，不上传到公开 GitHub 仓库。执行严格遵循教师手册：

1. 校验并解压原始 ZIP；
2. 从 H1 独立 Git 仓库读取两个完整课程提交；
3. 生成独立 `request-e12.json`；
4. 通过本组 `run_e11e12.py run` 执行五阶段流程；
5. 要求 `draft/full-check/incremental-check/repair/recheck` 五阶段齐全且最终状态为 `SUCCEEDED`；
6. 保存请求、退出码、原始控制台日志、构建日志、报告、Patch、验证和重检证据，并扫描运行日志中的疑似密钥。

服务器实际运行结果：

- 教师 ZIP SHA-256：`d9818c5f34d6ff5b6016222dabd7f56daca09ceaa5f525be214e146e3d485435`
- H1 base：`66a6dafcc20cea76bf017923d3db725d78407845`
- H1 target：`948a1d30cd758d32d45a50f788e5a95fb1d89c69`
- job：`job-fb3131ad0ff0439fa208b94a1df880b8`
- trace：`trace-f52b75910ab54846a9e8d6791761c16c`
- 退出码：`0`
- 五阶段：`draft → full-check → incremental-check → repair → recheck`
- 验证：`accepted=true`，重检 `MISSING=0`
- 运行日志扫描：`hits=0`、`errors=0`、退出码 `0`

## 公共准备

- 服务器独立克隆：`/root/devops-students/241880179/e13-b1`
- 准备时源码提交：`3b5ad072b0b5d574608115bd7868ca4ee70171be`
- `run_e11e12.py test`：54 项全部通过，退出码 `0`
- 固定 baseline 首次使用 Debian 官方源，在 Docker 构建阶段超过 600 秒，结果为 `FAILED/DRAFT_FAILED`；检查后无对应 Docker build 客户端或运行容器残留。
- 保留首次失败证据后，仅在隔离副本把 Debian 源改为清华镜像并使用新输出目录复跑；五阶段全部成功，job 为 `job-145fd4618a394f37a058b615e68c4e9c`，trace 为 `trace-86353b6dc5f24b48b3105c1c0be184d3`。

可提交的脱敏证据位于 `server-run/`；完整原始工作目录保留在课程服务器。教师 ZIP、上游源码和服务器凭据均未提交到公开仓库。
