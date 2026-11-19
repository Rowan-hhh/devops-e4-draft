# E13 B3 本地实现与证据契约

状态：`LOCAL_IMPLEMENTATION_COMPLETE`。C4、C7、H3 均为 `NOT_RUN`。尚未运行 Docker、服务器正式实验或正式 CI；mock、受控子进程、合成 Git 仓库及合成证据的本地测试不是服务器正式结果。正式服务器运行、证据归档、CI 链接和 B4 handoff 留待后续。

B3（241880360）负责 C4 超时与清理观察、C7 失败任务隔离、H3 教师 tiny-AES-c 项目的独立五阶段运行及交接。H3 是教师项目，不是 A/B 真实交换项目。

B2 代码提交 `5985d9e1b23a10e2b94ea83de9b99b5c7e33a7c3`；最终交付 `53f322d7e01f73ce03e99b87a579f285ecdb295e`；合并基线 `0ef30a1cba5d50007769dd22308a1f589c84a791`。B3 分支为 `e13-yrh-b3`。

## 验收与边界

- C4 使用独立请求和新输出目录，要求内层超时、外层失败、无成功候选，保留日志、退出码、两层结果、源码前后状态和原始进程及容器观察。完整一致的证据可以判定 PASS；缺失、矛盾或相关进程、准确验证容器仍运行时为 FAILED 或 BLOCKED。结论仅覆盖检查时刻的相关构建客户端和准确验证容器，不证明或清理 BuildKit 全局缓存；不执行 prune、不停止 Docker 服务、不清理其他任务容器。
- C7 先验证失败任务的真实身份、构建前失败和残留观察，再启动正常任务。两任务的 job、trace、目录、状态和产物必须隔离，所有声明 artifact 的 URI、大小及哈希必须一致，源码必须不变。verify 重新读取两任务的原始请求、结果、日志、退出码、源码状态、观察记录和 artifact，不信任摘要布尔值；正式 live work 须保留所有声明产物。
- H3 计划在系统临时目录安全检查教师 ZIP、来源、许可、Git 对象与祖先关系，绑定 ZIP、请求及项目身份。正式运行重新提取同一 ZIP，manifest 绑定实际五阶段、程序输出、补丁、验证、重检和源状态；MISSING 和 REDUNDANT 分开记录，剩余发现不得隐藏。

## 命令

实际入口：`python3 labs/e13/e13_b3.py --help`，子命令为 `c4`、`c7`、`h3`、`verify`。服务器模板中的路径须按实际环境替换；输出目录必须是仓库 `work/` 下尚不存在的子目录，项目和请求应能按服务的 `/course` 挂载解析。

```sh
python3 labs/e13/e13_b3.py c4 --entry run_e11e12.py --project <server-path-project> --request <server-path-request> --out work/e13-b3-c4
python3 labs/e13/e13_b3.py c7 --entry run_e11e12.py --project <server-path-project> --request <server-path-request> --failed-request <server-path-invalid-base-request> --out work/e13-b3-c7
python3 labs/e13/e13_b3.py h3 --zip <server-path-teacher-zip> --work work --out work/e13-b3-h3-plan
python3 labs/e13/e13_b3.py h3 --zip <server-path-teacher-zip> --work work --entry run_e11e12.py --run --out work/e13-b3-h3-run
python3 labs/e13/e13_b3.py verify --evidence work/e13-b3-c7/isolation-check.json --out work/e13-b3-c7-verify
python3 labs/e13/e13_b3.py verify --evidence work/e13-b3-h3-plan/plan.json --out work/e13-b3-h3-plan-verify
```

`<server-path-...>` 为占位符，执行前须替换。C4 的 verify 输入为案例目录中的带 `case` 字段的证据 JSON；H3 正式证据 verify 输入为包含 `case: H3`、原始 `plan` 对象和正式案例 `directory` 的索引 JSON。verify 输出目录也必须全新。实际文件名与失败证据以运行器输出为准。

本地回归：

```sh
python3 -m unittest discover -s labs/e13 -p 'test_*.py' -v
python3 -m unittest discover -s labs/e13e14/tests -p 'test_*.py' -v
python3 -m unittest discover -s labs/e11e12 -p 'test_*.py' -v
```

## 预期证据与交接

```text
work/<c4>/       request.json, console.log, exit-code.txt, result.json,
                 draft-build/, source-before.json, source-after.json,
                 processes-and-containers/
work/<c7>/       failed/, succeeded/, isolation-check.json
work/<h3>/       plan.json, request.json, input/（正式运行时）, run/,
                 source-before.json, source-after.json, evidence-manifest.json
```

上述是预期结构，不表示已产生证据。失败时保留已有输出与失败记录，不覆盖旧目录。向 B4 交接时应提供实际提交和运行环境、C4/C7/H3 结论与限制、请求及任务身份、来源与 Git 身份、阶段和日志、artifact 清单及哈希、剩余 findings、证据位置、CI 链接和未完成事项；这些字段待正式运行后据实填写。
