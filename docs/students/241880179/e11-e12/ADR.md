# ADR：E11 B2 使用固定 MD 与 B1 已验证 DRAFT 交接

## 状态

已接受并经本人复核。

## 背景

E11 B 轨由 DRAFT→MDFixer 组成。B1 已在 PR #18 和 CI run `42749304320` 中完成 DRAFT 两轮构建并交接成功镜像证据；B2 负责固定 MD→Patch→验证→重检。

服务器复跑 DRAFT 第二轮时，构建停在 Debian 软件包下载，属于外部软件源访问问题。该次中断不能作为成功证据，也不应掩盖 B2 自身是否正确。

## 决策

以 B1 已验证的 DRAFT CI 结果作为上游交接；B2 单独核对固定报告与目标提交身份，生成候选 Patch，并执行隔离构建、程序测试、头文件变化测试、重新扫描和 BuildChecker 全量重检。

只有五项验证全部通过且最终不存在 `MISSING` 时才接受修复。`REDUNDANT` 不由本次 MDFixer 修复。

## 结果

候选 Patch 补入 `config.h` 和 `extra.h`，五项检查全部通过，最终无 `MISSING`。服务器下载中断被如实记录，没有被写成成功构建。

## E12 B4：以原始 evidence 完成最终验收

### 状态

已接受并经本人复核。

### 背景与决策

E12 B4 不能只根据 B1–B3 的文字结论宣布完成。最终验收在 #23、#24 按顺序合入后重新运行真实项目，并同时绑定 A 组报告 SHA、B1 bundle、B2 修复结果、B3 API 契约、五阶段 job/trace 和阶段产物哈希。

采用独立 `e12_b4.py` 验收器检查严格阶段顺序、DRAFT 两轮语义、A 报告身份、修复计划、五项验证和最终无 `MISSING`。GitHub Actions 原始 artifact 是最终运行证据，仓库只归档核心 JSON、Patch、日志和哈希，不提交 sandbox、对象文件或 trace 大文件。

### 结果

最终 E11–E12 CI 与 E8–E10 回归均成功；真实项目五阶段全部通过，174 个产物，`accepted=true`，最终 `MISSING=0`。
