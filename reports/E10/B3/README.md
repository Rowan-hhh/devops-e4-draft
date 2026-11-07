# E10 B3 候选、输入与源文件基线

负责人：周逸涵，2418880300，B组/B轨，本阶段角色 E10 B3（接口与证据）。

## 输入交接

- 仓库：https://github.com/Rowan-hhh/devops-e4-draft.git
- 独立角色分支：`e10-zyh-b3`
- B1 合并后的 main：`470dfc79c8698874adddc3cc7b695d80b2425676`
- B1 最终提交：`756f6fe5a9a7539cbaf3fc8613c88d899d8145c5`
- B1 交接目录：`reports/E10/B1`
- B1 bundle：`reports/E10/B1/project.bundle`
- B1 环境镜像 ID：`sha256:94a15175783fe4f37f17f1ae1208edfbdd2524206304e1b1ce56295f27823c40`

按 B1 要求从 bundle 恢复样例，而不是重新初始化 Git：

```bash
git clone reports/E10/B1/project.bundle work/e10-B3-20261106-zyh-b3/e10-b1-project
git -C work/e10-B3-20261106-zyh-b3/e10-b1-project rev-parse HEAD
```

恢复后的内部 HEAD 为：`93ea08243be717cfe00502120ddebf2d090bdff7`。

## 四项交付物

- `fixed-md-report.json`：报告 commit 为 `93ea08243be717cfe00502120ddebf2d090bdff7`；
- `candidate.patch`：只将 `config.h` 加入 `main.o` 的依赖声明；
- `patch-plan.json`：记录目标 `main.o`、依赖 `config.h`、风格 `direct`；
- `source-before.Makefile`：Patch 生成前的原始 Makefile 字节快照。

报告发现为 `MISSING main.o/config.h` 和 `REDUNDANT main.o/unused.h`。源快照 SHA-256 为 `9206301c23ce4cb93c3fc1434037e475cf69f53e132dc541f6028d05e30258b2`，与 B1 交接一致。

## 验证

- 恢复项目工作区在采集前后均干净；
- 报告 commit 与恢复后的样例 HEAD 一致；
- `git apply --check candidate.patch` 通过；
- Patch 检查没有写回样例，源 Makefile 与快照保持一致；
- 本地采集使用 WSL2 GCC 13.3.0；B1 的固定镜像 ID、样例 bundle 和正式内部 HEAD 均按交接记录保留。

本次只完成 E10 B3 的输入、报告、Patch 和源文件基线；临时验证逻辑、错误拒绝、正确接受和最终 gate 属于 B2/B4 后续分工。
