# E8 B轨个人完整复跑

姓名/学号/校区：史美一 / 241880179 / 南京大学苏州校区。

小组/轨道：B组 / B轨。复跑分支：`student/241880179/e8-full-run`。

## 版本与环境

- 统一版本输入：`ee4a54807c6e3efb06689f09d17dec07530c0086`。
- 样例内部提交：`070a8913e408e73b442c939b769927b7d7f6a162`。
- 镜像：`course-e8e10:241880179`。
- 镜像 ID：`sha256:94a15175783fe4f37f17f1ae1208edfbdd2524206304e1b1ce56295f27823c40`。
- 服务器仓库：`/root/devops-students/241880179/draft-e8-full`。
- 服务器 OUT：`/root/devops-students/241880179/draft-e8-full/work/e8-B-personal-241880179-20261105-064601`。

本次从已经包含 E8 组内贡献和 E9 B1 合并结果的最新 `main` 建立个人分支。完整复跑使用全新的服务器仓库副本和 OUT，不覆盖原 E8 B1、B3 或 E9 证据。

## 完整流程结果

|步骤|实际结果|
|---|---|
|创建固定样例|成功；样例内部 Git HEAD 已记录，原始工作区干净|
|生成固定 MD 报告|精确得到 `MISSING main.o/config.h` 与 `REDUNDANT main.o/unused.h`|
|核对报告身份|报告 commit 与样例 HEAD 一致|
|生成候选 Patch|仅在 `main.o` 依赖中增加 `config.h`；风格为 `direct`|
|Patch 预检查|`git apply --check` 成功；原样例未修改|
|旧报告拒绝|返回 `STALE_REPORT`；原 Makefile 字节不变|
|副本应用与构建|Patch 在 `apply-demo` 中成功应用，构建通过，程序输出 `1`|
|应用后重新扫描|无 MISSING；`unused.h` 的 REDUNDANT 结果仍保留|
|源文件保护|配方字节保持不变；原样例输入哈希一致且 Git 工作区干净|
|统一测试|11 tests，OK，退出码 0|

最终机器可读结论见 `personal-full-run-summary.json`。8 个拆分步骤全部保存了脚本、日志及 `STEP_EXIT_CODE=0`；完整测试记录见 `unit-tests.log`。

## 证据说明

- `original-input/`：复跑前的受跟踪输入文件，不含内层 `.git` 和构建产物。
- `fixed-md-report.json`：固定 MD 输入及样例提交身份。
- `candidate.patch`、`patch-plan.json`：候选补丁与结构化定位计划。
- `expected-failure.json`：旧报告被拒绝的机器可读结果。
- `apply-result.json`、`apply-recheck.json`：副本应用、构建、运行和重新扫描结果。
- `input-file-hashes-before.json`、`input-file-hashes-after.json`：原样例输入保护证据。
- `runner/`、`steps/`：逐步执行脚本与真实日志。

完整服务器归档：`/root/devops-students/241880179/E8-personal-full-241880179-20261105-064601.tar.gz`。

归档 SHA-256：`49ba5d401784279385787f9aac39e75d6d6da9b41cc9082fbfa09d32265c0e8f`。

## 个人贡献与边界

此前已在组内版本中贡献 `StudentE8B3.test_report_identity_changes_even_when_findings_do_not`，其独立预期是：依赖发现相同但提交不同的两个报告仍必须分别绑定各自 HEAD。本次不重复实现组员算法，而是使用统一版本独立跑通报告、身份检查、Patch、预检查、旧报告拒绝、副本应用、构建运行和源文件保护全过程。

本次只完成 B轨个人实验和组内版本验证，不包含与 A组交换真实产物；跨组联调留待 E11—E12。

复核状态：已复核。本人已核对逐步日志、版本身份、报告发现、候选 Patch、拒绝结果、应用验证、输入保护和测试结论。
