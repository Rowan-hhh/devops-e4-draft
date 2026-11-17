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

实现位于 `labs/e13/e13_b1.py`，单元测试位于 `labs/e13/test_e13_b1.py`，CI 位于 `.github/workflows/e13-b1.yml`。CI artifact 会保存 C1/C2 的请求、日志、拒绝结果、Patch、验证和重检证据。

## 教师 jsmn 项目

jsmn 兼容性测试必须使用教师提供的项目包并单独归档，不能用公网项目或 A/B 真实项目替代。运行记录将在收到课程 E13 实验包中的 jsmn 源码及其说明后追加到本目录。
