# E12 B2：消费 A 组真实报告并完成修复验证

## 基线与输入

- 负责人：谢真婷（`241880610`）
- 分支：`e12-xzt-b2`
- 集成基线：`186dbf138de7fb7bb1dccb4fafa222e5ba27b830`
- B1 目标提交：`745ecf2621c8221b97bf0a5435ace50150ef57d4`
- B1 bundle SHA-256：`0a74f580219b55ab97119cdfa81f730f23fd0d5cbfbf2f986e4791110f3ce608`

B2 消费的是 A 组真实 `incremental-check.json`，没有使用 E11 的 `fixed-md.json`。输入报告的 SHA-256 为：

`66e3bfb2c39d4c8b0913d4b5afb269d284cb1369e05d68b4fd889170e1e38a83`

报告身份核对结果：`schema_version=e11e12-1`、`kind=incremental-check`、`status=SUCCEEDED`，外层和 `data.commit` 均为 `745ecf2621c8221b97bf0a5435ace50150ef57d4`。

报告来源任务为 `job-701e024edd564902a625716aa9547cf7`，`trace_id=trace-be8e398fc0564ebcb177991840937797`。

## A/B 交接内容

A 组真实报告只发现一项缺失依赖：

```text
helper.o -> output_format.h (MISSING)
```

B2 生成的 Patch 只修改 `Makefile` 的目标声明：

```diff
-helper.o: helper.c
+helper.o: helper.c output_format.h
```

编译命令、源文件和其他声明均未修改。

## 验证结果

执行器：`labs/e11e12/e12_b2.py`。它先校验 B1 bundle 和 A 组报告哈希，再从 bundle 的 target 提交建立全新工作副本，生成 Patch 并调用现有验证器。

| 检查项 | 结果 |
|---|---|
| Patch 可应用 | PASS |
| 构建 | PASS |
| 程序输出 | PASS，输出 `1` |
| 修改 `config.h` 后增量重建 | PASS，输出 `2` |
| 最终无 `MISSING` | PASS |
| B1 bundle 未被修改 | PASS |

最终结果为 `SUCCEEDED`。动态重检的 `findings` 为空，说明 `output_format.h` 已被正确补入 `helper.o` 的声明。

## 证据

- `incremental-check.json`：A 组真实输入报告
- `run/result.json`：B2 结构化结果
- `run/candidate.patch`：候选 Patch
- `run/repair-plan.json`：修复计划
- `run/validation/validation.json`：五项验证结果
- `run/recheck.json`：最终重检报告
- `run/validation/build.log`、`incremental.log`：构建及增量重建日志

下一步应将 B2 结果交给 B3 做 API/联调和契约检查；B2 不代替 B3 或 B4 执行最终五阶段验收。

