# E7 B1 正常候选与构建失败

## 目标

B1 负责核对服务测试，并用真实 Docker 流程验证两个场景：

1. 正常候选完成两轮构建，以生成的完整镜像 ID 禁网运行并输出 `hello E3`。
2. 在候选中显式注入 `RUN exit 23`，确认第一轮仍为 `MISSING_MAKE`，第二轮构建
   失败后立即停止，不检查镜像、不执行程序验证。

本阶段按分工表中途不需要与 A 组交接。

## 实现

- `scripts/run_e7_b_gate.py`：运行服务测试、正常候选和构建失败场景，输出
  `gate-result.json` 与 `results.csv`。
- `services/draft/tests/test_autobuild.py`：新增回归测试，确保第二轮构建失败时
  `_inspect_image` 和 `_verify_image` 都不会被调用。
- 构建失败是受控测试注入，不修改 `reports/E6/B2/candidate.Dockerfile`。

## 服务器命令

```sh
export DRAFT_BUILD_HTTP_PROXY=http://$(docker network inspect bridge \
  --format '{{(index .IPAM.Config 0).Gateway}}'):3142

python3 scripts/lab_cloud.py build \
  --image course1020-draft:e7-b1 \
  --out work/e7-b1-service-20261026 \
  --build-timeout 1200

python3 scripts/lab_cloud.py gate \
  --candidate reports/E6/B2/candidate.Dockerfile \
  --image course1020-draft:e7-b1 \
  --out work/e7-b1-20261026 \
  --build-timeout 1200
```

## 验收状态

| 项目 | 通过标准 | 状态 |
|---|---|---|
| 服务测试 | 服务镜像内测试全部通过 | PENDING |
| 正常候选 | 两轮完成、同一镜像 ID、禁网运行、输出匹配 | PENDING |
| 构建失败 | 第二轮退出非零、分类 `BUILD_FAILED` | PENDING |
| 停止验证 | 构建失败场景无 `verification`、无运行日志 | PENDING |
