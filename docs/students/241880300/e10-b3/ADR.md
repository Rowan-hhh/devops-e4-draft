# E10 B3 决策记录

## 选择

使用 B1 交付的 `project.bundle` 恢复样例，先核对 `git rev-parse HEAD`，再调用已有 `scan()` 生成报告，并以同一份报告调用 `patch()` 生成候选 Patch 和 plan。

## 版本与源保护

报告必须绑定内部样例 HEAD `93ea08243be717cfe00502120ddebf2d090bdff7`，不能使用外层仓库 main SHA。生成 Patch 前保存 Makefile 原始字节，生成过程不修改样例；`git apply --check` 只做语法检查。

## 范围边界

本分支只交付 B3 要求的四项输入与证据。Patch 的临时构建、程序测试、头文件变化重检、错误拒绝和最终 gate 由 B2/B4 继续完成。
