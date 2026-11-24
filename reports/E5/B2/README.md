# E5 B2：提示与候选获取

## 输入边界

本目录只记录 B2 的提示核对和候选获取，不记录 B3 的候选选择，也不替代 B4 的真实构建与运行验证。

| 项目 | 值 |
|---|---|
| 仓库 | `https://github.com/Rowan-hhh/devops-e4-draft.git` |
| 分支 | `e5-reproduction` |
| B1 源码提交 | `14cb9fef65746e8437d06752cb098171e10be9c5` |
| B1 报告提交 | `9417057` |
| 云端 B1 证据 | `/root/241880179/draft/work/e5-b1-final-20261022/` |
| 有效失败 | `make: not found`；Docker 构建退出码 `1` |
| 排除输入 | `/root/241880179/draft/work/e5-b1-infra-failed-20261022/`（Docker Hub 超时） |

## 两类提示核对

提示由仓库中的 `scripts/prepare_e5_prompts.py` 从 B1 的真实证据生成，原始提示文件保留在云端 B1 目录：

- 错误驱动：`/root/241880179/draft/work/e5-b1-final-20261022/iter-01/prompt-error-driven.txt`
  - 输入：失败 Dockerfile + `build-retry.log` 的末尾最多 50 行。
  - 不包含项目 README 上下文。
- 上下文驱动：`/root/241880179/draft/work/e5-b1-final-20261022/iter-01/prompt-context-driven.txt`
  - 输入：同一份失败 Dockerfile、同一份真实失败日志，并额外加入 `project/README.md`。

两类提示共同要求保留固定基础镜像 digest、项目文件、`WORKDIR`、`RUN make` 和 `CMD ["./hello"]`，安装必要构建依赖，不绕过真实构建，并返回一个完整 Dockerfile。原始提示字节由云端 B1 目录作为证据源；本目录的 `prompt-manifest.json` 记录来源和核对结论。

## 候选状态

本次取得三个候选：候选 1、2 来自错误驱动提示，候选 3 来自上下文驱动提示。每个候选都保存：

- 完整模型原始回复：`candidates/model-response-candidate-N.txt`
- 提取后的 Dockerfile：`candidates/candidate-N.Dockerfile`
- 来源、时间、候选编号和 SHA-256：`candidates/candidate-N-provenance.json`

候选 1–3 是本次 Codex 会话基于上述完整 B1 提示重新生成的模型回复；`fixtures/ci-candidates/DeepSeek-E5.Dockerfile` 仅是仓库中已有的 CI fixture，没有被冒充为本次模型回复。

三个候选当前均为 `RECEIVED_NOT_BUILT`。B2 不记录选择原因；B3 应依据 R1–R4 继续选择，B4 再执行真实构建和 `hello E3` 运行验证。
