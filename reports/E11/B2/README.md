# E11 B2 交付记录

- 姓名：史美一
- 学号：241880179
- 小组与角色：B 组 / E11 B2（固定 MD→候选 Patch→验证→动态重检）
- 工作分支：`student/241880179/e11-b2`
- 代码基线：B1 分支 `e11-e12-integration`，提交 `5c75e36e36a792ae4cec0bd05509118371670fb5`
- B2 独立测试提交：`ad7ab9b76d08d3416f3001f386ce2f272bfbb03a`
- 服务器个人镜像：`course-e11e12:241880179`
- 服务器个人镜像 ID：`sha256:b7b3426a362ad9fbbb06d22aa4c82ba19f2b6f1b36bd401ff2e70f90db02f863`

## 上游交接

B1 通过 PR #18 交接 DRAFT 构建结果：第一轮为 `MISSING_MAKE`，第二轮构建成功且镜像运行输出为 `1`。对应 CI run 为 `42749304320`，交接镜像 ID 为 `sha256:b5a9e75ae45b4f948a584f8a32d2833eeb687fc2965ab904da754d4efee5034a`。

本次服务器重复 DRAFT 构建时，Debian 软件源下载长时间无进度，因此未把该次中断运行记为成功证据。B2 按角色边界消费 B1 已验证的上游交接，独立执行修复、验证和动态重检。

## B2 实际结果

- 固定 MD 报告提交与目标提交均为 `4350fcdafaf4e708f51ea95f018211085dcd73d2`。
- 候选 Patch 为 `main.o` 增加 `config.h` 和 `extra.h` 两项直接依赖，不修改 recipe。
- `patch_applies`、`build`、`test`、`header_change`、`no_missing` 五项检查全部为 `true`。
- 验证结论为 `accepted=true`。
- BuildChecker 动态重检后没有 `MISSING`；`unused.h` 仍报告为 `REDUNDANT`，符合 MDFixer 只修复缺失依赖的范围。
- 完整测试为 11 项，全部通过，退出码 0。

## 独立贡献

新增 `StudentE11B2.test_two_missing_headers_share_one_safe_direct_patch`，验证同一目标同时缺少 `config.h` 和 `extra.h` 时，能够生成一次安全的 direct 风格 Patch，同时保持 Makefile recipe 字节不变。

## 证据索引

- `241880179-handoff.json`：结构化交接结论
- `fixed-md-input.json`：固定 MD 输入及版本身份
- `candidate.patch`、`repair-plan.json`：候选补丁与两项修复计划
- `validation/`：Patch 检查、构建、程序测试、头文件变化测试及重新扫描
- `final-full/`：最终 BuildChecker 图与 findings
- `unit-tests.log`、`unit-tests-exit-code.txt`：11 项测试记录
- `evidence-sha256.txt`：核心证据哈希
