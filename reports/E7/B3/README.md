# E7 B3 超时与整体 gate

## 任务结论

B3 在 B2 四场景 gate 的基础上增加了运行超时场景，并完成完整五场景验收：

```text
success, build-failed, wrong-output, invalid-candidate, timeout
```

最终 gate：`passed=true`，总退出码 `0`。

## 实现内容

- `services/draft/draft/autobuild.py`
  - 增加独立的验证超时参数。
  - 验证退出码 `124` 时分类为 `TIMED_OUT`。
  - 超时后读取 `cidfile`，执行 `docker rm -f`，并通过 `docker inspect` 确认容器已删除。
  - 保存 `verify-container-cleanup.json` 和 `verification.container_cleanup`。
- `services/draft/draft/cli.py`
  - 增加 `--verify-timeout` 参数。
- `scripts/run_e7_b_gate.py`
  - 增加 `timeout` 场景。
  - 将测试 fixture 的 `main.c` 替换为死循环，使候选构建成功但程序验证超时。
  - 校验 `TIMED_OUT`、验证退出码 `124`、容器清理和完整 gate 结果。
- `services/draft/tests/test_autobuild.py`
  - 增加超时清理回归测试。

候选 Dockerfile 未修改，原始候选 SHA-256 为：

```text
510dc459a9a3830aabdf35b32c15b0c22a3c3299982950e40378d4a3227b9788
```

## 服务器验收结果

服务镜像：`course1020-draft:e7-b3`

服务镜像 ID：

```text
sha256:fa225a9cb5473ec5714a6c8e1c58b95aced241e48f3b69143c94835d6a0ebe60
```

服务测试：`17 passed`

| 场景 | 退出码 | 状态 | trace_id | 结果 |
|---|---:|---|---|---|
| success | 0 | SUCCEEDED | `e6-b-9dd13102756f4253991728effdf33fb9` | 正常构建、禁网运行通过 |
| build-failed | 1 | FAILED | `e6-b-d21aff1603ed408e951920d155259b39` | `MISSING_MAKE → BUILD_FAILED`，停止验证 |
| wrong-output | 1 | FAILED | `e6-b-8ff6314ad25d4250a264325dc324e8bd` | `output_matches=false` |
| invalid-candidate | 1 | FAILED | `e6-b-e9e8425c059a4c6ca0d241919e6c1992` | 构建前拒绝，`attempts=[]` |
| timeout | 1 | FAILED | `e6-b-247b8550bdb249538108a78153c644a1` | `TIMED_OUT`，容器清理成功 |

### timeout 证据

- 镜像 ID：`sha256:1a54c04485c745f5827f805ab1bbb296d2118472ade85ca3a82a796d7edb28a4`
- 验证退出码：`124`
- 验证状态：`TIMED_OUT`
- 验证超时：`3` 秒
- 清理命令：`docker rm -f 9ebd8662a82442dbbc37359fca87f31bf8cfe11244f8bbdb9b0defd1063f862a`
- 清理退出码：`0`
- `removed`：`true`
- gate 结束后残留容器：`0`

## 原始证据

服务器证据目录：

```text
/root/E4-draft/work/e7-b3-service-20261026
/root/E4-draft/work/e7-b3-20261026/gate
```

其中保留 `gate-result.json`、`results.csv`、各场景原始 stdout/stderr、两轮构建日志、
`result.json`、`verification.json`、`verify-container-cleanup.json` 和退出码文件。

本分支基于 B2 提交 `d85fb51c24f71ecd3560572a1cd9bfc97f4d33e0`，B3 代码提交为
`b65c97dcdf13dac78c1bb28dc21d858a0a838fa1`。
