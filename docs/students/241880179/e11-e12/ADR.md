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
