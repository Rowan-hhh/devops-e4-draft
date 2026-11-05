5# E8 B3 固定 MD 报告与版本核对

负责人：241880179，B3（接口与报告）。本次阶段结果：PASS。

## 输入

- 仓库： https://github.com/Rowan-hhh/devops-e4-draft.git
- 个人分支：`student/241880179/e8-e10`。
- B1 输入提交：`593b40a176b0881f3b7ed072a4c6c4302957a07b`。
- B1 交接记录：`reports/E8/B1/241880360-handoff.json`。
- B1 原始样例：`/root/devops-students/241880360/draft/work/e8-B-manual.cGTRVM/project`。
- 固定样例提交：`aae7c9d74345872ef98f14558aaf4550f3d25d5a`。

在自己的服务器仓库 `/root/devops-students/241880179/draft` 中复制样例及其内部 Git 历史，保留 B1 原始证据。副本路径为 `work/e8-B-manual.t0bJlj/project`。未重新生成 fixture，因此样例提交保持与 B1 一致。

环境复用 B1 已验证的镜像，增加个人标签 `course-e8e10:241880179`，实际 ID 为 `sha256:94a15175783fe4f37f17f1ae1208edfbdd2524206304e1b1ce56295f27823c40`。

## 报告与核对结果

使用 `lab.scan(project)` 生成本次 `fixed-md-report.json`，从磁盘重新读取并检查 JSON 内容。

|类型|目标|依赖|
|---|---|---|
|MISSING|main.o|config.h|
|REDUNDANT|main.o|unused.h|

- 报告 `commit`、样例内部 HEAD 和 B1 固定样例提交三者相同。
- `actual` 为 `main.o: [config.h, main.c]`、`helper.o: [helper.c]`。
- `declared` 为 `main.o: [main.c, unused.h]`、`helper.o: [helper.c]`。
- 发现集合精确等于上述两条，没有额外发现。
- 报告序列化、重新读取一致。
- 采集前后副本全部受跟踪输入文件 SHA-256 相同，副本工作区干净。
- B1 原始样例工作区在本次操作后仍干净。
- `report-identity.json` 的六项检查均为 true，`passed=true`；报告生成步骤退出码为 0。

本报告来自本地 GCC 教学采集器，属于 E8 固定输入，不代表已经接入 A 组远程服务。

## 个人贡献与测试

在 `labs/e8e10/test_profile.py` 新增 `StudentE8B3.test_report_identity_changes_even_when_findings_do_not`。测试只在临时样例中增加不改变依赖的源码注释并创建新提交，独立断言两版发现均为已知 MD/RD、提交不同、新报告绑定新 HEAD，旧报告仍保留旧提交。测试还检查 JSON 往返和样例工作区状态。

服务器实际执行：

```bash
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -v "$PWD:/course" -w /course course-e8e10:241880179 \
  python3 -m unittest discover -s labs/e8e10 -p test_profile.py -v
```

初次结果：`Ran 9 tests in 0.204s`，`OK`，退出码 0。随后将上传测试文件的 Windows 换行符统一为 LF；最终再次运行得到 `Ran 9 tests in 0.208s`，`OK`，退出码 0，Linux Git 差异为新增 30 行且 `git diff --check` 通过。B1 原有 8 项测试保留。

本次采集时外层 HEAD 为 B1 输入提交，个人测试文件尚未提交；`source-state.json` 记录采集时的状态及文件哈希，`test_profile.before-lf.py.txt` 保留初次执行的测试文件字节。`test-source-state.json` 和 `unit-tests-final.log` 记录换行格式统一后的最终测试源码哈希与结果。`lab.py` 和 `run_lab.py` 与输入提交一致。

## 交给 B2

服务器证据目录：`/root/devops-students/241880179/draft/work/e8-B-manual.t0bJlj`。

结构化交接：`reports/E8/B3/241880179-handoff.json`。使用该目录的 `project` 与 `fixed-md-report.json` 作为同版本输入，生成 `candidate.patch` 和 `patch-plan.json`。本次 B3 未对交接样例生成或应用补丁，也未代做 B4 拒绝/保护验证。候选补丁按 E8 要求处理 MISSING，保留 RD 和编译配方。

执行补丁步骤前，B2 应重新核对报告 commit、当前项目 HEAD 和干净工作区；若样例变化，应重新采集报告，不能改写旧报告的 commit 绕过检查。

`work/` 保存原始证据；本目录同时保存报告、身份检查、文件哈希、源码状态和测试日志的小型副本。当前已归档结果来自服务器实际运行；GitHub Actions 结果需按本次个人分支提交另行核对，PR 尚未创建。
