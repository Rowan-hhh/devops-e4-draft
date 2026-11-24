# 决策记录

背景与约束：B轨需要根据固定 MD 报告生成最小 Patch，同时保证失败候选不会修改原项目。报告还必须与受测项目的提交一致。

选择与替代方案：候选先在独立 sandbox 中验证，通过 Patch 应用、构建、功能测试、头文件变化和再次扫描后才写回。没有直接在原目录试改，也没有在验证失败后手工恢复文件。

共享变量处理：E9 中 direct 修改目标依赖行，macro 修改专用变量定义，mixed 保留宏引用并在目标依赖行补充 `config.h`。如果变量被多个目标共享，优先避免直接修改共享变量，以免扩大影响范围。

失败保护：验证前保存 Makefile 字节。错误测试和无效 Patch 两种场景都要求 `accepted=false`、`rollback=true`、`source_unchanged=true`，并用 `cmp` 再次核对。

代价与覆盖范围：sandbox 会增加一次文件复制和构建开销，但可以把候选验证与真实写回隔离。本次只覆盖课程给出的直接、宏和混合声明，不声称支持所有 Makefile 语法。

验证命令与实际证据：E10 证据位于 `work/e10-B-manual.txx1eQ`。`results.csv` 三行均为 True，`gate.json` 为 `passed=true`，最终 BuildChecker 没有 MISSING，坏 Patch 拒绝后 Makefile 字节比较退出码为 0。
