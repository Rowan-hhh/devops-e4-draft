# E8 B2 候选 Patch 交付

## 输入

- 上游分支：`student/241880179/e8-e10`
- 上游提交：`113643e748d7cf6503bb4a383b00c58b16ff195e`
- 固定报告：`reports/E8/B3/fixed-md-report.json`
- 样例项目提交：`aae7c9d74345872ef98f14558aaf4550f3d25d5a`
- 服务器原始证据目录：`/root/devops-students/241880179/draft/work/e8-B-manual.t0bJlj`

## 核对结果

报告中的 `commit` 与样例项目 HEAD 一致。报告包含两条发现：

- `MISSING main.o -> config.h`：本次候选唯一修复项。
- `REDUNDANT main.o -> unused.h`：保留，不自动删除。

候选只向 `main.o` 的依赖列表追加 `config.h`，不改变原有编译命令、`helper.o` 规则或其他文件。B3 交接记录已经证明候选生成前源项目工作区干净且输入字节未改变。

## 交付物

- `candidate.patch`：统一格式候选补丁。
- `patch-plan.json`：目标、依赖、声明风格和保留项。
- `validation.json`：版本身份、修改范围和源文件保护检查。

本次 B2 只生成候选，不直接写回服务器原始 `project/`。下一步由 B4 在临时副本中执行 `git apply --check`、构建、程序测试、头文件变化测试和重新扫描，并根据全部检查决定接受或回滚。
