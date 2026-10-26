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
| 服务测试 | 服务镜像内测试全部通过 | PASS，`14 passed` |
| 正常候选 | 两轮完成、同一镜像 ID、禁网运行、输出匹配 | PASS |
| 构建失败 | 第二轮退出非零、分类 `BUILD_FAILED` | PASS |
| 停止验证 | 构建失败场景无 `verification`、无运行日志 | PASS |

## 最终结果

E7 B1 最终结论为 **PASS**。机器可读汇总见
`reports/E7/B1/acceptance.json`。

| 项目 | 结果 |
|---|---|
| 已测试代码提交 | `5c82d9067c651b2b3256350098d17af16d41782b` |
| 服务镜像 ID | `sha256:6906971e0479d7573627eab17e1187d10588b8456e4497f16867e765de9709d7` |
| gate 总退出码 | `0` |
| gate 总状态 | `passed=true` |
| 正常候选 trace_id | `e6-b-620bdd19b6614f57a8983d26c41c278e` |
| 正常候选镜像 ID | `sha256:5a3e4045d5c07613f6d4c66bbd059eb032311eaaa5cfd65f44aaa8d8c4ddca81` |
| 正常候选运行 | 退出码 `0`，stdout `hello E3\n`，stderr 空 |
| 构建失败 trace_id | `e6-b-befa9d46160c409b839b6a8af8319e7d` |
| 构建失败两轮 | `MISSING_MAKE` → `BUILD_FAILED`，第二轮退出码 `1` |
| 构建失败后验证 | 无 `verification`、无 `verify*` 文件 |
| 密钥扫描 | PASS，退出码 `0` |
| 残留运行容器 | `0` |

服务器证据目录：

```text
/root/E4-draft/work/e7-b1-service-20261026
/root/E4-draft/work/e7-b1-20261026
```

本地原始证据备份：`tmp/e7-b1-241880179-evidence.tar.gz`，SHA-256：

```text
50de5730d41ea717c5f5a05fbe1184d7c9df8acd094b82f9f1143a594883a368
```

按照 E7 分工，B1 阶段不需要中途向 A 组交接；B3 完成整体 gate 后再发送一次
中途状态。
