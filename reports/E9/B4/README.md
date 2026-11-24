# E9 B4 实验记录

- 当前分支：`e9-yrh-b4`
- B3 上游：`0636c8fb950e4048e186b8960a28fc0edfb04070`
- B2 最终基线：`127b945bb91f4d56f176955d726b8004c87620a6`
- B4 实现提交：`6752443e560c9a7e5e482fb9adda882c8b6a40d0`

`acceptance.json` 的 `baseline_commit` 为上述 B2 基线，`execution_commit` 为上述 B4 实现提交。B2 归档中的旧提交描述不影响本次核对，本次以上述完整 SHA 为准。

分别初始化 direct、macro、mixed 原始样例，输入 SHA-256 与 B1 交接一致，报告绑定各自本地真实 HEAD；未修改 B3 报告的 commit。

三种风格的 Patch 均通过 `git apply --check`，仅在隔离副本中实际应用、构建和运行。direct 在目标依赖行追加 `config.h`，macro 在 `DEPS` 中追加，mixed 在目标行的 `$(HEADERS)` 后追加。recipe 字节保持一致；构建和运行退出码均为 0，运行输出均为 `1`；应用后复扫无 MISSING，仍保留 `unused.h` 的 REDUNDANT。

原始输入在候选生成前后、apply 检查后及隔离构建后哈希一致，Git 状态干净，未被修改。各风格的 Patch、plan、input、recheck、source-state 及 apply-check/build/run 日志已归档。`unit-tests.log` 记录 14 项测试通过，测试退出码为 0。

已归档证据生成时，`reports/E9/B4` 原本不存在。脚本拒绝覆盖已有输出目录；后续复跑须使用新的非现有目录，例如执行前确认 `work/e9-b4-recheck` 不存在：

```bash
python3 -B labs/e8e10/verify_e9_b4.py \
    --out work/e9-b4-recheck
```
