# E13 B2：C3/C5 失败门禁与 H2-inih 独立运行

负责人：周逸涵（241880300）
分支：`e13-zyh-b2`
执行基线：B1 PR #27 合并提交 `5b8bb237a44ff3888f0b2748b641c916d47adce0`

## C3 产物哈希篡改

以 B1 交付的 `reports/E13/B1/a-input/incremental-check.json` 原始 SHA-256
`66e3bfb2c39d4c8b0913d4b5afb269d284cb1369e05d68b4fd889170e1e38a83` 为旧哈希，在隔离目录末尾追加换行后重放。篡改件 SHA-256 为
`3bd0b8f88f3ebd0cf360db61b19fae6715e695adebcc6c0d58df9fba62365a8d`。系统返回
`ARTIFACT_HASH_MISMATCH`，`accepted=false`，`repair_started=false`。
原件、篡改件、前后 SHA 和拒绝结果均保存在 `C3-artifact-hash-tamper/`。

## C5 错误补丁与回滚

在 B1 E12 项目 bundle 的独立克隆上使用 `invalid.patch`（SHA-256：
`e54c8e2ce43635bd3b6260915f1e21711b53d5c48aca8cb9f1c3fc6bac9a86cd`）。
`git apply --check` 返回无效补丁错误，`accepted=false`、`rollback=true`、
`source_unchanged=true`。项目 HEAD 前后均为
`745ecf2621c8221b97bf0a5435ace50150ef57d4`，逐文件 SHA 清单在
`C5-invalid-patch/result.json`，验证结果在
`C5-invalid-patch/validation/validation.json`。

## H2-inih

教师发放包仅在服务器隔离目录使用，没有提交源码或 ZIP。独立 Git 仓库的两个提交为：

- base：`aafc740a2cac05a74541abede93b7d59ed23b87f`
- target：`3aadb81763c79651e4dfa99b725ba921ee2b8a39`
- 请求：`H2-inih/request-e12.json`
- job：`job-1ed771c2018040a08f97c338d1310559`
- trace：`trace-a85266b25b754e5ebb539b471790d803`
- 五阶段：`draft → full-check → incremental-check → repair → recheck`
- 状态：`SUCCEEDED`，退出码 `0`，程序输出 `1`
- 验证：`accepted=true`，最终 `MISSING=0`

`recheck.json` 中保留了最终的 `REDUNDANT main.o/unused.h` 观察结果；本门禁关注缺失依赖为零，并未删除该真实结果。
完整脱敏运行证据在 `H2-inih/`；复制的 `base-project`、`target-project`、sandbox 和 `.git` 元数据没有归档到仓库。

## 环境记录

服务器 Docker 镜像 ID：`sha256:9b4546beda2654110c7080e3fd55deffb1f21b95cfdbacd8df76ec65abc14ae2`。
首次 Docker Hub 元数据请求失败的日志与同 digest 镜像站重跑成功的日志均在 `environment/`。

教师发放包 SHA-256：`d9818c5f34d6ff5b6016222dabd7f56daca09ceaa5f525be214e146e3d485435`。

服务器执行 `python3 run_e11e12.py test` 共 54 项，全部通过，退出码为 `0`；原始日志在 `environment/e11e12-tests.log`。

## 交接

请 B3 从本分支/PR 读取 `handoff.json`，核对 C3/C5 判定、H2 的 base/target、job/trace、五阶段结果和证据目录，再继续 E13 汇总。
