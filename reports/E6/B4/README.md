# E6 B4 最终验收

## 当前状态

本分支以 B3 提交 `661afe1f81638709121b58419fb5f9f20c2de034` 为基线。
B1–B3 的仓库交付已经核对；B4 新增了镜像运行约束回归测试和 E6 证据一致性校验脚本。

本地 Windows 环境没有 Docker，不能把服务器重建和运行结果写成已通过。完成下列
Linux 服务器命令后，才可将 B4 最终状态标记为 `PASS`。

## 已核对的输入

| 项目 | 值 |
|---|---|
| B3 分支 | `e6-xiezhenting-b3` |
| B3 提交 | `661afe1f81638709121b58419fb5f9f20c2de034` |
| 候选文件 | `reports/E6/B2/candidate.Dockerfile` |
| 候选 SHA-256 | `510dc459a9a3830aabdf35b32c15b0c22a3c3299982950e40378d4a3227b9788` |
| B3 镜像 ID | `sha256:410e69896d1aa14db9fc9a27ba45c6c9971413594bdd6fb6da89882038fc09e3` |
| B3 运行结果 | 退出码 `0`，stdout `hello E3\n`，stderr 空 |
| B3 原始证据 | `/root/E4-draft/work/e6-b3-20261026/evidence/b3-validation` |

## B4 新增测试

`services/draft/tests/test_autobuild.py::test_verification_runs_exact_image_offline_with_limits`
检查最终验证必须：

- 使用构建得到的完整 `sha256:` 镜像 ID，而不是可变标签；
- 使用 `--network none`；
- 保留 CPU、内存和 PID 限制；
- 退出码为 `0`、输出匹配且 stderr 为空。

## 服务器最终验收命令

以下命令均在仓库根目录运行。每个 `--out` 目录必须是尚不存在的新目录。

```sh
git rev-parse HEAD
sha256sum reports/E6/B2/candidate.Dockerfile

python3 scripts/lab_cloud.py build \
  --image course1020-draft:e6-b4 \
  --out work/e6-b4-service-20261026 \
  --build-timeout 1200
echo "SERVICE_BUILD_EXIT_CODE=$?"

python3 scripts/lab_cloud.py e6 \
  --candidate reports/E6/B2/candidate.Dockerfile \
  --image course1020-draft:e6-b4 \
  --out work/e6-b4-own-20261026 \
  --build-timeout 1200
echo "OWN_CANDIDATE_EXIT_CODE=$?"
python3 scripts/verify_e6_b_evidence.py \
  --run-dir work/e6-b4-own-20261026/evidence

python3 scripts/lab_cloud.py e6 \
  --replay \
  --image course1020-draft:e6-b4 \
  --out work/e6-b4-replay-20261026 \
  --build-timeout 1200
echo "REPLAY_EXIT_CODE=$?"
python3 scripts/verify_e6_b_evidence.py \
  --run-dir work/e6-b4-replay-20261026/evidence

python3 scripts/secret_scan.py . --history
```

`--candidate` 与 `--replay` 是互斥参数，因此必须分两次执行；`--replay` 使用仓库中
保存的教学候选，不表示自己的候选。B4 同时运行两种模式是额外的交叉检查。

## 通过标准

| 验收项 | 通过标准 | 当前状态 |
|---|---|---|
| 新增测试 | 服务镜像内全部 pytest 通过 | 待服务器重建确认 |
| 服务镜像重建 | `lab_cloud.py build` 退出码 `0` | PENDING |
| 自己的候选 | 两轮构建、同一镜像 ID 禁网运行、输出匹配 | PENDING |
| `--replay` | 两轮构建、同一镜像 ID 禁网运行、输出匹配 | PENDING |
| 密钥扫描 | 未发现密钥 | PENDING |

如果第二轮再次因 `deb.debian.org` 超时，保留完整日志并将其记为基础设施失败；不要
修改 `reports/E6/B2/candidate.Dockerfile`，否则候选 SHA 会变化。网络恢复或配置宿主
可达代理后，换一个新的 `--out` 目录重新执行。
