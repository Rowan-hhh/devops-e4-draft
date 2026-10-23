# E5 B3：候选选择与服务器验证

B3 负责候选选择和服务器验证，不代替 B4 最终验收。

## 输入来源

- B1 源码提交：`14cb9fef65746e8437d06752cb098171e10be9c5`
- B1 报告提交：`9417057ba1fad4e1e0a8e96bda8b3e58384014e4`
- B2 候选提交：`561e51f1e072fe9c3d3e563402edbab13604afe0`

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

## 当前状态

`SELECTED_PENDING_SERVER_VALIDATION`。尚未执行候选构建，尚未取得镜像 ID，尚未执行 `hello E3` 运行验证；不得描述为已成功。

服务器验证完成后，需要补充 evidence 路径、构建命令与退出码、完整 `build.log`、镜像标签和完整 image ID、运行命令与退出码、stdout、stderr，以及 `hello E3` 精确匹配结果。上述验证数据尚未产生。
