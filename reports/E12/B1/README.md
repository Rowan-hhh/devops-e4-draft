# E12 B1：维护项目、DRAFT 成功与交接

本目录保存从本组 E7 使用的 fixtures/draft 派生的“E12 B 组维护项目”。
它不是外部生产项目，没有复制 integration-sample，没有用 prepare.py 生成维护历史。
最终服务器 B1 结果为 SUCCEEDED；交接对象为 A 组及后续 B2。
A 组真实报告尚未收到，B2 最终 Patch、B3 API 联调、B4 五阶段最终验收均未执行。
本次归档不运行 Docker，不暂存、提交或推送。

## 项目与版本

来源仓库：https://github.com/Rowan-hhh/devops-e4-draft.git 。
来源路径 fixtures/draft，最初引入提交为 c7ec20de19d2554f2273d2d76f3739541acedf0c，
E7 基线为 84152137c120883432fe6b6525ba9ca92a71a332，
本次派生来源外层提交为 d1dbc4665dcaa690bcf9c322d4930358cd579d2e。
最终执行代码提交另为 8cd9224f32f73594c1c921cd4553cedb3760b55f，不混同来源提交。

| 角色 | 完整提交 SHA | 实际演进 |
|---|---|---|
| P0 | 4eb43414f37440b4f4dcd9dcd0702f955d9b78b2 | 原样导入 E7 fixture 输入并增加 SOURCE.md |
| P1 / base | 0b62c79a6adb4cd913a814068074575afdbbd18b | main.c 读取 VALUE，helper.c 实际输出，正确声明两对象依赖 |
| P2 / target | 745ecf2621c8221b97bf0a5435ace50150ef57d4 | helper.c 实际使用 output_format.h，暂保留 helper.o: helper.c |

三个真实提交使用本人身份与实际时间，base 是 target 祖先；无日期覆盖或历史改写。
P2 是明确记录的课程受控依赖演进，本说明不代表 A 组已检测到某种结果。
Dockerfile.reference 仅为 P0 原始来源文件，不是 E12 候选，也不进入 DRAFT 构建上下文。

## 本地检查与服务器执行

本地 P0 使用原始 make 和 ./hello，输出 hello E3 加一个换行；P1/P2 使用
make clean、make app、./app、make clean，输出严格为 1 加一个换行，stderr 为空，退出码 0。
这些本地 C/Make 检查与 mock 测试不冒充服务器 DRAFT 证据。

服务器真实失败与修正按顺序保留：

1. 环境镜像构建访问 Docker Hub 的 Docker CLI 元数据超时。
2. Docker CLI 改为同 digest 的 DaoCloud 镜像地址后成功构建；没有修改固定摘要。
3. 从 bundle 恢复项目后缺少本地 Git identity，第一次 B1 调用在 DRAFT 前拒绝。
4. 补齐本地身份，旧候选第二轮因 Debian 官方源下载缓慢超过 600 秒，结果 TIMED_OUT、source_unchanged=true。
5. 人工修正唯一允许的安装 RUN：固定 TUNA HTTPS Debian/Security 源，update/install 使用 IPv4 和 3 次重试，仅安装 gcc make libc6-dev，并清理 apt 列表。
6. 新候选最终完成 DRAFT 两轮构建和镜像运行；旧失败目录没有被覆盖或写成成功。

成功原始入口：run/success/result.json、run/success/draft.json。
第一轮 build_exit_code=1、failure_class=MISSING_MAKE；第二轮 build_exit_code=0；
镜像禁网运行 exit_code=0、actual_output 为 JSON 字符串 "1\n"、output_matches=true、stderr 为空。
顶层 source_unchanged=true、a_group_report_received=false。

- DRAFT trace_id：e6-b-1e1d0b56397b406a9d599f5553d03993。
- 服务环境：course-e11e12:241880360，ID sha256:a9c65eab021262a76f2025a42a9526aa5d793ee4f2224696bbb6419d0daf80e0。
- 候选镜像：sha256:71af06d98998e249bb1229fe71118fa45b1d56a40cb460b2687f6b5c9f8138f6。
- 候选文件 SHA-256：c7b2ba5babf97c0c413583d908ab372b224a6351f127124b068f1607aefc44af。
- success/source-before.json 和 source-after.json 的 SHA-256 均为 eca324d730f9739f3f0433c8b67fe98d8abf90f1825884b26d6c2d4e6964ed7d。
- 服务器完整测试：46 项、OK、退出码 0，见 run/metadata/unit-tests.log 与 unit-tests-exit-code.txt。
- 本人提供的最新 CI 结果：E11-E12 run 42975542918 success；E8-E10 run 42975542951 success。本次仅归档该确认信息，未重新查询 CI。

## A 组及 B2 的恢复与核验

所有交接路径相对外层仓库根目录，完整入口为 handoff.json。
恢复使用已归档 project.bundle，不需要信任或访问未归档的服务器绝对路径。
目的目录必须不存在；A 组可自行替换恢复目录并保留自己的本地 Git 身份。

```sh
python3 -B -c 'import hashlib,json,pathlib; p=pathlib.Path("reports/E12/B1"); s=json.loads((p/"project-source.json").read_text()); assert hashlib.sha256((p/"project.bundle").read_bytes()).hexdigest()==s["bundle_sha256"]'
git bundle verify reports/E12/B1/project.bundle
git clone reports/E12/B1/project.bundle data/e12-b-real-project/repo
git -C data/e12-b-real-project/repo rev-parse --is-shallow-repository
git -C data/e12-b-real-project/repo merge-base --is-ancestor 0b62c79a6adb4cd913a814068074575afdbbd18b 745ecf2621c8221b97bf0a5435ace50150ef57d4
git -C data/e12-b-real-project/repo checkout --detach 745ecf2621c8221b97bf0a5435ace50150ef57d4
git -C data/e12-b-real-project/repo rev-parse HEAD
git -C data/e12-b-real-project/repo status --porcelain=v1 --untracked-files=all
python3 -B -c 'import hashlib,json,pathlib; s=json.loads(pathlib.Path("reports/E12/B1/project-source.json").read_text()); p=pathlib.Path("data/e12-b-real-project/repo"); assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==v for n,v in s["project_files"].items())'
```

预期：非浅仓库、祖先命令退出 0、HEAD 为 target、状态为空、文件哈希一致。
bundle SHA-256 为 0a74f580219b55ab97119cdfa81f730f23fd0d5cbfbf2f986e4791110f3ce608。
源码 SHA、来源、完整历史与候选交给 A 组生成真实报告，随后由 B2 消费真实报告。

## 归档范围和执行边界

run/README.md 解释原始成功、超时、环境、前置拒绝及传输材料。
archive-manifest.json 覆盖本目录全部最终文件，排除自身，逐项记录相对路径、SHA-256 和字节数。
原始证据在整理前后逐字节哈希一致；传输排除的 Git 元数据及 tar 校验范围均见 run/README.md。

B1 只校验来源/身份、隔离 target、调用 vendor DRAFT 并核对原项目不变。
精确候选白名单不允许任意 RUN、源码覆盖或绕过 make。
没有生成 incremental-check.json、candidate.patch、repair.json、recheck.json、full-check.json。
已有 CI 教学五阶段结果不等于本项目的 A/B 交换或 B4 最终验收。

project-source.json 当前是执行后的归档状态，server_draft_executed=true；
执行提交中的前置清单仍由原 Git 历史保留。B1 当前代码要求运行前清单为 false，
因此本归档清单不作为直接重跑入口；复现时应在独立检出执行提交，使用其原始运行前清单、
同一 bundle 与全新输出目录，不应修改本归档或重建项目提交。
