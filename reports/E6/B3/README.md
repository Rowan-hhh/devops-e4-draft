# E6 B3 镜像运行与报告校验

## 结论

本报告对应 E6 B2 候选分支 `e6-yironghui-candidate` 的提交
`94c771a695147366d11a8ee11f52d63bc73f5503`。候选文件保持不变，SHA-256 为：

```text
510dc459a9a3830aabdf35b32c15b0c22a3c3299982950e40378d4a3227b9788
```

B3 的无网络运行验证结果为 **PASS**：

- 构建退出码：`0`
- 镜像 ID：`sha256:410e69896d1aa14db9fc9a27ba45c6c9971413594bdd6fb6da89882038fc09e3`
- 运行命令包含 `--network none`、`--cpus 1`、`--memory 128m`、`--pids-limit 64`
- 运行退出码：`0`
- stdout：精确为 `hello E3\n`
- stderr：空
- `output_matches`：`true`

## 构建说明

按 E6 B1 流程对当前候选执行了两轮自动构建。第一轮按预期因缺少 `make`
失败，第二轮因服务器访问 `deb.debian.org` 的网络速度过低超时；两次失败证据
均保留在服务器目录中：

```text
/root/E4-draft/work/e6-b3-20261026/evidence
/root/E4-draft/work/e6-b3-20261026-rerun/evidence
```

为完成 B3 的镜像运行校验，随后使用相同固定基础镜像、相同候选步骤顺序和同一
构建上下文，仅将 Debian 源切换到服务器可达的镜像源后完成重建。候选 Dockerfile
本身没有修改，候选 SHA 与 B2 交接值一致。成功构建日志和运行证据位于：

```text
/root/E4-draft/work/e6-b3-20261026/evidence/b3-validation
```

该适配只解决服务器软件源连通性，不改变 `WORKDIR`、`COPY`、`RUN make` 或
`CMD ["./hello"]` 的候选行为。完整机器可读结果见同目录的 `result.json`（本仓库
副本为 `reports/E6/B3/result.json`）。

## B3 交付物

- `result.json`：镜像 ID、构建/运行退出码、实际输出、`output_matches` 和证据路径。
- `image_id.txt`：完整镜像 ID。
- `verify.stdout.log`、`verify.stderr.log`：无网络运行原始输出。
- `build-summary.json`：构建方式和 B1 两轮状态摘要。

本阶段只完成 B3 的镜像运行与报告校验，不代表 B4 的测试与最终集成验收已经完成。
