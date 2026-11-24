# E9 B2 个人贡献

## 贡献内容

B2 在 E9 B3 三种声明风格报告的基础上，补充了一个独立测试：当变量声明中重复出现同一个依赖时，声明图应先去重，Patch 仍应识别 `main.o -> config.h` 的 MISSING，并保持 `macro` 风格的修改位置。

测试文件：`labs/e8e10/test_profile.py`

测试名称：`StudentE9B2.test_macro_duplicate_dependencies_are_normalized_before_patch`

## 独立预期

- `DEPS = main.c unused.h unused.h` 的声明图只保留一个 `unused.h`。
- 报告仍识别 `config.h` 为 MISSING。
- Patch 计划的风格仍为 `macro`。
- 候选生成阶段不修改源 Makefile。

## 上游交接

- 上游分支：`student/241880300/e8-e10`
- 上游提交：`0636c8f`（以远程完整 SHA 为准）
- B3 已交付 direct、macro、mixed 三份报告和核对证据。

本目录记录 B2 的独立测试贡献。完整的 E9 B 阶段报告、三种 Patch 和运行证据继续使用 B3 交接的输入，并在本分支完成核对后统一提交。
