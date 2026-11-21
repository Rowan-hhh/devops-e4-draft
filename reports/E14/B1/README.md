# E14 B1：LOCAL_PREPARATION_ONLY

E13 基线 `77da560719fe7835c227a289b6bc99295fa5abcc` 已锁定；E14 最终候选尚未确定。固定样例和单容器正式运行均为 NOT_RUN，四服务为 BLOCKED_ON_B2_HANDOFF。本地契约测试不是正式运行。

单容器固定样例、四服务固定样例与 B3 的真实 A/B 项目是三类独立验收。正式四服务验收依赖 B2 部署交接；B4 负责故障恢复及最终发布。

下面仅为未来命令模板，尚未执行。首先在干净、已提交的集成仓库运行 preflight；准备固定样例后检查请求，然后使用全新证据目录执行单容器运行和核验。该运行会调用 Docker，只能在获准的正式服务器执行。

```sh
python3 labs/e13e14/e14_b1.py preflight
python3 labs/e13e14/e14_b1.py inspect-request --request data/integration-sample/e12.json
python3 labs/e13e14/e14_b1.py single-run --request data/integration-sample/e12.json --out work/e14-b1-single-01
python3 labs/e13e14/e14_b1.py verify-single-run --evidence work/e14-b1-single-01
python3 labs/e13e14/e14_b1.py verify-service-handoff --handoff work/b2-handoff.json
```

运行包装器对原始输入仓库采集前后快照，结论仅为运行前后边界状态一致，不证明运行期间不存在瞬时修改。隔离副本的修复由 Patch、validation 和 recheck 核验。

正式运行时，包装器将每个声明产物复制到 `sealed-run/files/`，并在 `sealed-run/manifest.json` 记录原始声明和封存字节的哈希；`run/` 是可变工作目录。验证器读取封存副本。`execution.json` 和失败时的 `failure.json` 保留运行、封存及采集 after 的错误。

B2 交接包放在 `work/`，以 JSON 记录 `candidate_commit`、`compose`、`rendered_config`、`logs`、`image` 和 `health`。前两项及每份日志均为包含包内相对 `path`、`bytes`、`sha256` 的对象；渲染配置是 `docker compose config --format json` 的实际文件。镜像使用显式 tag、image_id 和 repo_digest，或填写 repo_digest_absent_reason。核验只证明交接包内部一致，不能代替实际部署证明。

正式证据归档后必须将 workflow 的准备态门禁升级为正式证据门禁，不能永久要求 NOT_RUN。

`sealed-inputs/` 保存执行请求、候选 Dockerfile、固定报告、Git bundle 和输入 manifest。默认 `verify-single-run` 离线恢复 bundle 到系统临时目录，核对提交祖先关系、tree、模式、blob 与边界快照；可选 `--live-source` 额外核对原始仓库。bundle 证明封存的 Git 对象与历史，before/after 记录运行边界，两者均不能证明运行期间没有瞬时修改。manifest 哈希提供内部一致性，须由可信交接或外部发布记录保护其身份，不能单凭可同时更改的文件证明来源。

正式归档可提交 `sealed-inputs/`、`sealed-run/` 及必要包装层证据和 manifest，包括 `source.bundle`；不提交 bundle 恢复出的 `.git` 或源码工作树、教师 ZIP、原始 `data/`，也不归档 mutable `run/` 的嵌套 Git 工作副本。若组内最终禁止 bundle，离线证据能力应标为 BLOCKED，等待组内确认替代证明。

候选文件的连续运行边界：当前 `single-run` 保存并封存候选 Dockerfile 的字节和 SHA-256，但 E11/E12 流水线执行时仍按请求中的原始 `candidate` 路径读取文件。运行前、结果及后续核验能够发现边界哈希不一致，不能证明运行期间没有发生替换后又恢复的瞬时修改；该限制没有被现有技术机制完全消除。

正式运行必须在受控服务器的专属工作目录中执行，运行前确认没有相关并发任务，确保运行期间其他任务不能写入候选输入；候选文件及其父目录须采用只读或严格受控权限，并在运行后立即核对候选字节及 SHA-256。不能满足这些条件时正式结果必须标记 BLOCKED，不能判 PASS。这项限制涉及连续运行期间的不变性证明；`sealed-inputs` 仍用于离线复核实际封存的输入字节。
