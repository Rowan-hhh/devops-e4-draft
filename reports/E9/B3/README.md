# E9 B3 三种输入报告与版本核对

负责人：周逸涵，2418880300，B组/B轨，本阶段角色 B3（接口与输入）。

## 输入与交接

- 仓库：https://github.com/Rowan-hhh/devops-e4-draft.git
- 个人分支：`student/2418880300/e8-e10`
- B1 交接：`reports/E9/B1/241880179-handoff.json`
- B1 服务器 OUT：`/root/devops-students/241880179/draft-e9-b1/work/e9-B1-20261105-051015`
- B1 样例镜像：`course-e8e10:241880179`

B1 交接明确给出了三个独立样例的输入哈希和内部 HEAD：

| 风格 | 样例内部 HEAD | 输入报告 |
|---|---|---|
| direct | `6018ff0bfdfb0d163ca871ae6640bb9c7b5a02be` | `direct-input.json` |
| macro | `c8337b58f5823f82ff16805b7d9ffe9d72833b4a` | `macro-input.json` |
| mixed | `980140007fc4c51faa30121bedde5d654285921d` | `mixed-input.json` |

## 生成结果

`direct-input.json`、`macro-input.json`、`mixed-input.json` 均按 `lab.scan()` 的 E8-E10 报告格式生成。三份报告都记录了：

- `main.o` 缺失真实依赖 `config.h`；
- `main.o` 多声明冗余依赖 `unused.h`；
- `helper.o` 的 `helper.c` 声明与实际依赖一致；
- 报告 `commit` 与对应 B1 样例 HEAD 一致。

`commit-check.json` 的三行均为 `report_commit_matches_sample_head=true`、`input_sha256_matches_handoff=true`，整体 `passed=true`。

当前工作区未直接挂载 B1 的服务器 OUT，因此本次使用 `fixture()` 重放三种样例，并逐文件核对 B1 交接中的 SHA-256；重放项目的临时 HEAD 只保留在本地证据中，未冒充正式样例 HEAD。生成器同时支持 `--samples-root`，在服务器样例目录可用时会直接检查每个项目的 `git rev-parse HEAD`。

本地重放证据目录：`work/e9-B3-20261105-051015-replay/`（按仓库约定不提交）。

## 可重复命令

```bash
PYTHONPATH=labs/e8e10 python3 labs/e8e10/generate_e9_b3.py \
  --handoff reports/E9/B1/241880179-handoff.json \
  --reports-out reports/E9/B3 \
  --replay-root work/e9-B3-20261105-051015-replay
```

若已取得 B1 的原始样例目录，可改用：

```bash
PYTHONPATH=labs/e8e10 python3 labs/e8e10/generate_e9_b3.py \
  --handoff reports/E9/B1/241880179-handoff.json \
  --reports-out reports/E9/B3 \
  --samples-root <包含-direct、macro、mixed-目录的路径>
```

本次没有生成候选 Patch、plan 或应用演示；这些属于 B2/B4 的后续范围。
