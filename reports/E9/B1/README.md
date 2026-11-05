# E9 B1 环境同步与三种样例初始化

负责人：史美一，241880179，南京大学苏州校区，B组/B轨，本阶段角色 B1。

## 结果与输入版本

E9 B1 初始化通过。最新 `origin/main` 在本次同步时为 `df9a2fe2331b4de82f1209be82a0c35ea562597c`；初始化代码与测试的实际执行提交为 `45c83b180645283ee61665852596db75d49ff414`。E8 个人交付仍在原分支，本次从实际 main 创建独立的 E9 B1 工作目录，保留原目录中尚未提交的修改。

- 仓库：https://github.com/Rowan-hhh/devops-e4-draft.git
- 本次交付分支：`student/241880179/e9-b1`。
- 服务器仓库：`/root/devops-students/241880179/draft-e9-b1`。
- E9 OUT：`/root/devops-students/241880179/draft-e9-b1/work/e9-B1-20261105-051015`。
- 环境镜像：`course-e8e10:241880179`。
- 镜像 ID：`sha256:94a15175783fe4f37f17f1ae1208edfbdd2524206304e1b1ce56295f27823c40`。

## 初始化范围

新增 `labs/e8e10/init_e9_b1.py`，复用课程 `fixture()` 生成三个独立项目。检查原始声明文本、解析后的依赖、内部 Git 提交、干净工作区和受跟踪输入文件哈希，保存原始 Makefile 快照。已有 OUT 会被拒绝，防止覆盖旧证据。

|风格|原始声明|样例内部提交|
|---|---|---|
|direct|`main.o: main.c unused.h`|`6018ff0bfdfb0d163ca871ae6640bb9c7b5a02be`|
|macro|`DEPS = main.c unused.h`，`main.o: $(DEPS)`|`c8337b58f5823f82ff16805b7d9ffe9d72833b4a`|
|mixed|`HEADERS = unused.h`，`main.o: main.c $(HEADERS)`|`980140007fc4c51faa30121bedde5d654285921d`|

三种原始样例中，main.c 包含 config.h，Makefile 均尚未声明 config.h。上述状态用于后续 B3 报告采集及 B2 补丁生成，B1 不提前修复。

## 实际验证

服务器容器内执行：

```bash
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -v "$PWD:/course" -w /course course-e8e10:241880179 \
  python3 -m unittest discover -s labs/e8e10 -p test_profile.py -v

docker run --rm --network none --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -v "$PWD:/course" -w /course course-e8e10:241880179 \
  python3 labs/e8e10/init_e9_b1.py \
  --out /course/work/e9-B1-20261105-051015 --smoke
```

单元测试结果：9 tests，OK，退出码 0（main 原有 7 项加本次 B1 的 2 项）。新增测试为 `StudentE9B1.test_three_pristine_styles_are_separately_versioned` 和 `StudentE9B1.test_existing_evidence_directory_is_not_overwritten`。

三种风格分别复制到 OUT/smoke/ 下进行真实 `make app` 和 `./app` 检查，三个输出均为 `1`。构建副本与待交接的原始项目分离；原始项目的输入哈希保持不变，内部 Git 工作区均干净。首次构建成功不代表缺失依赖已修复。

初始化步骤输出 `E9_B1_INITIALIZATION_PASS`，服务器最终核对输出 `E9_B1_SERVER_PASS`。环境工具版本、真实镜像详情、源码提交及各样例提交均已归档；本记录不将服务器测试结果表述为已完成 GitHub Actions 验收。

## 交给 E9 B3

结构化交接：`reports/E9/B1/241880179-handoff.json`。使用 OUT 下的 `direct/`、`macro/`、`mixed/`，复制项目时保留各自的 `.git` 历史。

B3 接续生成 `direct-input.json`、`macro-input.json`、`mixed-input.json`，并分别核对报告 commit 与对应项目 HEAD。不要把外层源码提交作为样例 HEAD，也不要把三个样例的提交混用。

本次未生成三份输入报告、候选 Patch、plan 或应用演示。B2 接续补丁生成，B4 接续检查、应用演示和最终整理。

## 证据

本目录保存交接 JSON、sample-manifest.json、环境检查、初始化与单元测试日志、镜像详情及原始 Makefile 快照。完整原始项目、内部 Git 历史和构建副本保存在服务器 OUT 与本地 work 归档中。

服务器归档：`/root/devops-students/241880179/E9-B1-20261105-051015-evidence.tar.gz`。

归档 SHA-256：`475eeb161e505cd6824101249b23eabdd258c260b6fe269b12f3eb77f62137b7`。

GitHub Actions 结果、PR 链接与合并状态按后续实际记录补充。
