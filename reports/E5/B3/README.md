# E5 B3：候选选择与服务器验证

B3 负责候选选择和服务器验证，不代替 B4 最终验收。

## 输入来源

- B1 源码提交：`14cb9fef65746e8437d06752cb098171e10be9c5`
- B1 报告提交：`9417057ba1fad4e1e0a8e96bda8b3e58384014e4`
- B2 候选提交：`5a1f6923d8edabf64371260f4797e607736f8cf0`

| 候选 | SHA-256 |
|---|---|
| candidate-1 | `ede21b0fab394071641526e2fccefc41565efb00de6fb54d9d5b906aebeb535d` |
| candidate-2 | `027d8aabcd8d192cac5353831afe51c7d600fabf28528936ea9c9f715d3fb95c` |
| candidate-3 | `a78a103b453f83a7405172a850f73cd88a4da9addb654a918118f37554a30a24` |

## R1–R4 选择过程

- **R1：** 本次 B1 证据只记录错误 Dockerfile 的失败构建，没有证据证明三个候选已在本次迭代中构建，因此三者均保持可选。候选 1 与既有 DeepSeek fixture 字节相同；这里只记录内容相同这一事实，不据此声称它已在本次迭代中构建。
- **R2：** 三个完整 Dockerfile 归一化后并不相同，不存在完整候选的多数一致；只有候选 1、2 都采用 `build-essential`。
- **R3：** 三个候选都针对 `make: not found`，无法唯一决定。
- **R4：** 采用透明的工程性 tie-break，选择候选 2。

候选 2 使用候选 1、2 共同采用的 `build-essential`，固定 `FROM` digest，并保留 `WORKDIR`、`COPY`、`RUN make` 和 `CMD ["./hello"]`。依赖安装放在 `COPY` 之前，源码变化时可复用依赖层。没有加入绕过构建、伪造输出或无关指令。所选原文件为 [candidate-2.Dockerfile](../B2/candidates/candidate-2.Dockerfile)，未另存副本。

## B3 服务器验证

状态为 `SELECTED_SERVER_VALIDATED`。在仓库提交 `9c78b4256f84ba2aaea9558660b4ed8b8e2ac27a` 上验证 candidate-2，候选 SHA-256 为 `027d8aabcd8d192cac5353831afe51c7d600fabf28528936ea9c9f715d3fb95c`。

最终结果依据后台 no-cache 构建证据：构建于 `2026-10-24T08:06:35Z` 开始、`2026-10-24T09:35:46Z` 结束，build exit code 为 `0`。APT 输出 delayed-item warnings，但 `RUN make` 成功，镜像成功导出。镜像标签为 `e5-b3-candidate-2:241880360`，完整 image ID 为 `sha256:9c28c8c7e22a15185e1ebec50759467079333db9d9cfff5572509a018216048a`，架构为 `amd64`。

前一次前台构建因切换为可断线后台运行而中断；`build-interrupted.log` 不作为最终结果。最终依据是 `/root/241880360/e5-b3-20261024T075232Z/evidence/build.log`，其 SHA-256 为 `eac1142b0f243d40e08be9895c2b81bfc136df4e25280aaecf176934301c877b`。

运行 exit code 为 `0`；stdout 精确输出 `hello E3` 并以换行结束，stderr 为空，输出匹配结果为 `true`。原始结构化证据见 [server-validation.json](./server-validation.json)。

B3 服务器验证通过不等于 B4 最终验收；下一步交由 B4。
