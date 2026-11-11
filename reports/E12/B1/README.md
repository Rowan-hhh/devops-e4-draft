# E12 B1 项目准备：等待服务器 DRAFT

本目录保存 E12 B 组维护项目的来源、完整历史和手工候选。
项目从本组 E7 使用的 `fixtures/draft` 派生，不是外部生产项目，
没有复制 integration-sample，也没有运行 prepare.py 或教学历史生成函数。

本轮只实施 B1 的项目准备和独立入口。本地 C/Make 检查已完成；
**没有运行 Docker 或正式服务器 DRAFT，没有服务器成功结论。**
A 组真实报告尚未收到。B2 最终 Patch、B3 API 联调、B4 五阶段验收均未执行。
本目录没有正式 handoff、run/ 或 archive-manifest；这些等待真实服务器运行。

## 来源与三个真实提交

来源仓库为 https://github.com/Rowan-hhh/devops-e4-draft.git 。
来源外层提交：`d1dbc4665dcaa690bcf9c322d4930358cd579d2e`。
来源路径：`fixtures/draft`；该 fixture 最初在 E4 引入，E7 与当前来源字节一致。
完整来源字段、原始文件哈希、提交身份与实际时间见 `project-source.json`。

| 角色 | 完整提交 SHA | 变化 |
|---|---|---|
| P0 | `4eb43414f37440b4f4dcd9dcd0702f955d9b78b2` | 原样导入 fixture 输入，增加 SOURCE.md |
| P1 / base | `0b62c79a6adb4cd913a814068074575afdbbd18b` | 演进为可配置数值输出程序，helper.c 实际负责输出 |
| P2 / target | `745ecf2621c8221b97bf0a5435ace50150ef57d4` | 输出格式提取到 output_format.h，实际 include 并使用 |

三个提交均由 `241880360 <241880360@smail.nju.edu.cn>` 实际创建，未覆盖日期或改写历史。
P0 用原始 `make` / `./hello` 检查，输出 `hello E3\n`；原 fixture 没有 app 目标。
P1/P2 用 `make clean`、`make app`、`./app`、`make clean` 检查，stdout 为 `1\n`，
stderr 为空，退出码为 0，清理后 Git 状态为空。这些是本地原生构建检查，不是服务器证据。

P1 声明完整。P2 暂保留 `helper.o: helper.c`，是明确记录的受控依赖演进；
后续由 A 组实际检测、B2 修复。本说明不是 A 组检测结论。
项目保留的 `Dockerfile.reference` 只是 P0 来源文件，不是 E12 候选，也不进入构建上下文。

## 文件

- `project.bundle`：三个提交及 main/HEAD 的完整 Git 历史。
- `project-source.json`：来源、实际 SHA、身份、文件哈希、预期行为、bundle SHA-256。
- `candidate.Dockerfile`：人工准备，只增加经过审核的系统依赖安装 RUN。
- `candidate-provenance.json`：人工来源和候选哈希；不是新模型回复。
- `b1-request.json`：可移植相对路径，所有 SHA 都来自实际提交。

`data/`、`work/` 继续由外层 .gitignore 忽略；不添加 gitlink，不追踪嵌套 .git。
这些新归档文件目前待人工审核，外层未暂存、未提交、未推送。

## 在本机、服务器或 A 组机器恢复

从包含本实现和归档的外层仓库根目录执行；目的目录必须不存在：

```sh
python3 -B -c 'import hashlib,json,pathlib; p=pathlib.Path("reports/E12/B1"); s=json.loads((p/"project-source.json").read_text()); assert hashlib.sha256((p/"project.bundle").read_bytes()).hexdigest()==s["bundle_sha256"]'
git bundle verify reports/E12/B1/project.bundle
git clone reports/E12/B1/project.bundle data/e12-b-real-project/repo
git -C data/e12-b-real-project/repo rev-parse --is-shallow-repository
git -C data/e12-b-real-project/repo merge-base --is-ancestor 0b62c79a6adb4cd913a814068074575afdbbd18b 745ecf2621c8221b97bf0a5435ace50150ef57d4
git -C data/e12-b-real-project/repo checkout --detach 745ecf2621c8221b97bf0a5435ace50150ef57d4
git -C data/e12-b-real-project/repo rev-parse HEAD
git -C data/e12-b-real-project/repo status --porcelain=v1 --untracked-files=all
```

预期：非浅仓库、祖先命令退出 0、HEAD 等于 target、状态为空。
A 组也可用任何新的恢复目录，使用同一组 SHA 和源码哈希核验；不得重新初始化来替代恢复。
A 组保留自己的本地 Git 身份。仅本人运行 B1 入口前，设置嵌套项目本地身份：

```sh
git -C data/e12-b-real-project/repo config --local user.name 241880360
git -C data/e12-b-real-project/repo config --local user.email 241880360@smail.nju.edu.cn
```

## 后续服务器验证（尚未执行）

将审核后的外层实现及归档传至 Linux Docker 服务器，按上述方式恢复项目，
外层 Git 本地 user.name 必须为本人学号。确认没有日期覆盖环境变量，不重新创建项目提交。
先运行单元测试，再构建个人服务镜像，最后只运行 B1：

```sh
python3 -B -m unittest discover -s labs/e11e12 -p 'test_*.py' -v
python3 run_e11e12.py build
python3 run_e11e12.py e12-b1 --request reports/E12/B1/b1-request.json --out work/e12-B1-241880360-<实际运行标识>
```

`<实际运行标识>` 必须替换成新的标识，不要直接作为 shell 输入。
宿主外层根目录绑定到 `/course`；请求里的相对路径统一相对该根解析。
例如 `data/e12-b-real-project/repo` 映射为 `/course/data/e12-b-real-project/repo`。
请求没有 `/Users/...` 路径。原始日志中的实际绝对路径不影响恢复。

broken/candidate 使用相同固定 digest FROM、WORKDIR、COPY、RUN make app 和 CMD。
候选只在 make 前增加 gcc/make/libc6-dev 安装，不改源码或运行输出。
第一轮必须到达 make 并得到 MISSING_MAKE；第二轮退出 0；镜像以真实 ID 禁网运行，
stdout 严格为 `1\n`，stderr 为空，退出 0。还必须证明原项目受跟踪文件、HEAD、refs、状态和身份未变。
基础镜像平台与可拉取性仍须服务器核验；网络或软件源失败不能计作有效首轮失败。

入口仅调用 vendor DRAFT，不调用 pipeline、检测、修复或 API。
不使用完整 mode=e12 作为 B1 证据。现有 CI 的教学五阶段结果只用于回归，不能替代本项目服务器证据。
正式执行后才能归档原始日志、镜像 ID、外层执行 SHA、退出码，创建 handoff 与哈希清单。
