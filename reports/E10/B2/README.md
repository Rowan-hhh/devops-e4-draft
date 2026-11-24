# E10 B2 临时环境验证逻辑

负责人：史美一，241880179，南京大学苏州校区，B组/B轨，本阶段角色 E10 B2（验证逻辑）。

## 输入与版本

- 仓库：https://github.com/Rowan-hhh/devops-e4-draft.git
- 个人分支：`student/241880179/e10-b2`。
- 实际执行源码提交：`8e4cba9156b82e207b1eef21cd19b7bc89eedef8`。
- 上游 B3 提交：`dec8476f9f01b1162a226acc46ebcad6d6097a73`。
- B1 合并后的 main：`470dfc79c8698874adddc3cc7b695d80b2425676`。
- B1/B3 样例内部提交：`93ea08243be717cfe00502120ddebf2d090bdff7`。
- 镜像：`course-e8e10:241880179`。
- 镜像 ID：`sha256:94a15175783fe4f37f17f1ae1208edfbdd2524206304e1b1ce56295f27823c40`。
- 服务器仓库：`/root/devops-students/241880179/draft-e10-b2-run2`。
- 服务器 OUT：`/root/devops-students/241880179/draft-e10-b2-run2/work/e10-B2-241880179-20261106-075539`。

B2 从 B3 的真实角色分支建立，使用 B1 `project.bundle` 恢复内部 Git 历史，并核对 B3 的 `fixed-md-report.json`、`candidate.patch`、`patch-plan.json` 与 `source-before.Makefile`。本次没有重新生成或人工改写上游报告、候选和 plan。

## 输入核对

`b3-input-check.json` 中六项检查全部通过：

- 报告 commit 等于恢复项目 HEAD；
- 发现精确为 `MISSING main.o/config.h` 和 `REDUNDANT main.o/unused.h`；
- plan 精确定位 `main.o/config.h`，风格为 `direct`；
- `source-before.Makefile` 与恢复项目字节一致；
- 验证前项目干净；
- `git apply --check` 成功。

原 Makefile SHA-256 为 `9206301c23ce4cb93c3fc1434037e475cf69f53e132dc541f6028d05e30258b2`。

## validate() 实际验证结果

|案例|Patch 检查|构建|程序测试|头文件变化|重新扫描|结果与源文件状态|
|---|---:|---:|---:|---:|---:|---|
|故意错误测试预期|通过|通过|失败|通过|无 MISSING|拒绝；rollback=true；源字节不变|
|正确候选|通过|通过|通过|通过|无 MISSING|接受；只写回通过验证的 Makefile|
|无效 Patch|失败|未继续|未继续|未继续|未继续|拒绝；已接受 Makefile 保持不变|
|编译失败候选|通过|失败|未继续|未继续|未继续|拒绝；rollback=true；原项目干净|

正确候选接受后，源 Makefile SHA-256 为 `ab35bda3d5bf1ba02394a04bddcb8ec23a2e3ba67d7be9338be3e49fed9b1d5d0`。接受路径的 `patch_applies`、`build`、`test`、`header_change`、`no_missing` 五项检查全部为 true。之后再验证无效 Patch，已接受版本字节保持不变。

## 个人独立贡献

在 `labs/e8e10/test_profile.py` 新增 `StudentE10B2.test_compilation_failure_candidate_rolls_back_source_bytes`。该测试构造一个格式正确、能够通过 `git apply --check`、但把 `main.o` 编译配方改为 `false` 的候选；独立预期是构建失败、`accepted=false`、`rollback=true`、源 Makefile 字节不变且项目工作区干净。

该测试既在 GitHub Actions 提交 `8e4cba9` 上通过，也在课程镜像完整测试中通过。服务器完整测试结果为 19 tests、OK、退出码 0。

## 证据与边界

- `accept/`：正确候选的 validation、构建、增量重编译和重新扫描证据。
- `reject-test/`：错误测试预期的拒绝、构建、增量测试和重新扫描证据。
- `reject-patch/`：无效 Patch 拒绝结果。
- `reject-compile/`：编译失败候选拒绝结果。
- `source-before.Makefile`、`source-after-accept.Makefile`：接受前后字节基线。
- `runner/`、`steps/`：7 个拆分步骤及真实日志，全部 `STEP_EXIT_CODE=0`。
- `b2-validation-summary.json`：机器可读阶段汇总。

完整服务器归档：`/root/devops-students/241880179/E10-B2-241880179-20261106-075539.tar.gz`。

归档 SHA-256：`931a61b47058b6e67ce35f21c5272fbc9d4de88162bf2fa1a169e0d792622733`。

B2 负责验证可复用的 `validate()` 流程；B4 仍需从已合并上游独立执行最终接受/拒绝 gate、BuildChecker 重检和最终交付。本次不把 B2 证据冒充 B4 最终 gate。

当前 B3 提交尚未合入 `main`，因此 B2 最终 PR 应等待 B3 先创建并合并 PR，再同步最新 `main`。

复核状态：已复核。本人已核对 B1/B3 版本身份、四类 validation、源文件保护、19 项测试、交接内容和归档哈希，确认记录与实际执行结果一致。
