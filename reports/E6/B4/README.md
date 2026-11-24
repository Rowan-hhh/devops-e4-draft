# E6 B4 最终验收

## 验收结论

本分支以 B3 提交 `661afe1f81638709121b58419fb5f9f20c2de034` 为基线。
B4 最终验收结论为 **PASS**。测试代码提交 `00ea304aa2a38709b01e68f0b0a23c0f821447cd`
已在 Linux 服务器真实重建服务镜像，并分别运行自己的候选和 `--replay` 候选；两次
都完成 `MISSING_MAKE` 到成功构建的两轮流程，并以完整镜像 ID 禁网运行成功。

机器可读汇总见 `reports/E6/B4/acceptance.json`，原始证据保存在服务器 `work/` 和
本地备份包 `tmp/e6-b4-241880179-evidence.tar.gz`。

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

新增的两个 B4 回归测试检查：

- 使用构建得到的完整 `sha256:` 镜像 ID，而不是可变标签；
- 使用 `--network none`；
- 保留 CPU、内存和 PID 限制；
- 退出码为 `0`、输出匹配且 stderr 为空。
- 显式构建代理会记录在 `docker build` 命令中，且不会改写候选 Dockerfile。

服务器重建服务镜像后的测试结果为 `13 passed`。

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
| 新增测试 | 服务镜像内全部 pytest 通过 | PASS，`13 passed` |
| 服务镜像重建 | `lab_cloud.py build` 退出码 `0` | PASS |
| 自己的候选 | 两轮构建、同一镜像 ID 禁网运行、输出匹配 | PASS |
| `--replay` | 两轮构建、同一镜像 ID 禁网运行、输出匹配 | PASS |
| 密钥扫描 | 未发现密钥 | PASS，退出码 `0` |

## 最终结果

| 项目 | 结果 |
|---|---|
| 服务镜像 ID | `sha256:776421800c05e95fbe2bd23a19f34645ef8204cd170ccbe98f8188f33d5f9216` |
| 自己的候选 trace_id | `e6-b-874c4bfe00484f3ebe5e018129625305` |
| 自己的候选镜像 ID | `sha256:5acbc1a54d9e74237e5589dd8269b8f845b3c306260902e669ac5fb264bf215f` |
| 自己的候选运行 | 退出码 `0`，stdout `hello E3\n`，stderr 空 |
| replay trace_id | `e6-b-0bda836558874f9183f530c2e018cc4b` |
| replay 候选 SHA-256 | `ede21b0fab394071641526e2fccefc41565efb00de6fb54d9d5b906aebeb535d` |
| replay 镜像 ID | `sha256:4a9a5ed5044ab3ddb5207e3a880770dd649bcc75f1fbcc157cbe2db82c0c9770` |
| replay 运行 | 退出码 `0`，stdout `hello E3\n`，stderr 空 |
| 残留运行容器 | `0` |
| 证据包 SHA-256 | `a8957efa0e7b01da3b451691d00d822a92340fc671a29cd4b09423b5baa2a549` |

如果第二轮再次因 `deb.debian.org` 超时，保留完整日志并将其记为基础设施失败；不要
修改 `reports/E6/B2/candidate.Dockerfile`，否则候选 SHA 会变化。网络恢复或配置宿主
可达代理后，换一个新的 `--out` 目录重新执行。

仓库支持通过 `DRAFT_BUILD_HTTP_PROXY` 显式传入无凭据 HTTP(S) 构建代理。代理值会
写进保存的 `docker build` 命令，便于审计；它不会改写候选 Dockerfile。服务器默认源
确实超时时，可启动仓库内的限域镜像代理并重跑：

```sh
nohup python3 scripts/debian_mirror_proxy.py --listen 0.0.0.0 --port 3142 \
  > work/e6-b4-proxy.log 2>&1 &
echo $! > work/e6-b4-proxy.pid
export DRAFT_BUILD_HTTP_PROXY=http://$(docker network inspect bridge \
  --format '{{(index .IPAM.Config 0).Gateway}}'):3142
```

本次第一次直接运行确实在第二轮得到 `BUILD_TIMEOUT`，证据目录为
`work/e6-b4-own-20261026/`。随后使用上述显式代理在新目录重跑成功；候选 SHA-256
保持为交接值，构建命令和代理访问日志均已保存。
