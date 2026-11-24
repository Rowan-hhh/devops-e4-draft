# E7 B2 输出不符与无效候选

## 完成内容

B2 在 B1 的 gate 基础上增加并验证了两个场景：

1. `wrong-output`：候选正常构建并运行，但 gate 将期望输出设为 `wrong E3`，实际输出为
   `hello E3`，因此记录 `output_matches=false` 和 `RUNTIME_VERIFICATION_FAILED`。
2. `invalid-candidate`：将候选 `CMD ["./hello"]` 改为
   `CMD ["./not-a-real-program"]`，在 `validate_candidate` 阶段拒绝，未进入任何构建轮次，
   `attempts=[]`，没有镜像检查和程序验证。

原有 `success` 和 `build-failed` 场景保持不变。gate 现在完整覆盖四个场景：

```text
success, build-failed, wrong-output, invalid-candidate
```

## 代码交付

- `scripts/run_e7_b_gate.py`
  - 增加 `wrong-output`、`invalid-candidate` case。
  - 校验输出不符时的镜像 ID、运行退出码、实际输出和 `output_matches=false`。
  - 校验无效候选的 `INVALID_CANDIDATE`、`attempts=[]`，并确保未产生验证结果。
  - 保存每个场景的 `gate-result.json`、`results.csv`、命令、退出码、标准输出、标准错误和原始 evidence。
- `services/draft/tests/test_autobuild.py`
  - 增加无效候选构建前拒绝测试。
  - 增加运行输出不符分类测试。

## 服务器验收

服务镜像：`course1020-draft:e7-b2`

服务镜像 ID：

```text
sha256:3abf8497c8470fa9f9956583b723442939f22c928115a2cdd574f45628595455
```

服务单元测试：`16 passed`

gate 总结果：`passed=true`，总退出码 `0`，运行后残留容器 `0`。

| 场景 | 工作流退出码 | 状态 | trace_id | 关键结果 |
|---|---:|---|---|---|
| success | 0 | SUCCEEDED | `e6-b-3ae250160afc4a0bbf836c695a65eff7` | 两轮构建成功，禁网运行输出 `hello E3` |
| build-failed | 1 | FAILED | `e6-b-85878c4e481842768bac71a41eeec186` | `MISSING_MAKE` → `BUILD_FAILED`，停止后续验证 |
| wrong-output | 1 | FAILED | `e6-b-b071140a26064f0b9811e28dd945b150` | 实际 `hello E3`，`output_matches=false` |
| invalid-candidate | 1 | FAILED | `e6-b-d3e707fa480c4f08aa3e0b3eb5e99057` | `INVALID_CANDIDATE`，`attempts=[]` |

正常场景候选 SHA-256：

```text
510dc459a9a3830aabdf35b32c15b0c22a3c3299982950e40378d4a3227b9788
```

正常场景镜像 ID：

```text
sha256:fa47fc66960900c5694acac73d7f0aaac6be4bfa3e37b46079c92b9a2f496ebd
```

wrong-output 场景验证结果：

```json
{
  "expected_output": "wrong E3\n",
  "actual_output": "hello E3\n",
  "exit_code": 0,
  "stderr": "",
  "output_matches": false
}
```

invalid-candidate 场景结果：

```json
{
  "failure_class": "INVALID_CANDIDATE",
  "candidate_errors": ["CMD [\"./hello\"] is required"],
  "attempts": []
}
```

## 原始证据

服务器完整证据目录：

```text
/root/E4-draft/work/e7-b2-service-20261026
/root/E4-draft/work/e7-b2-20261026/gate
```

其中保留 `gate-result.json`、`results.csv`、四个场景的 `stdout.log`、`stderr.log`、
`exit-code.json`、构建日志、验证日志、`result.json` 和 `SHA256SUMS`。

本 B2 分支基于 B1 提交 `42065eaf265da55ee05dcc60c27cfefb7f524c5f`。
