# E13 B3 正式服务器证据与 B4 交接

正式 C4、C7、H3 案例及独立 verify 均 PASS。结构化结果和交接分别见 [result.json](result.json)、[handoff.json](handoff.json)，原始证据见 [server-run](server-run/README.md)，归档校验见 [archive-manifest.json](archive-manifest.json)。分支 `e13-yrh-b3`，代码提交 `6876b98c31f9c270a27c2dbc93df9447ae30203e`；B2 代码提交 `5985d9e1b23a10e2b94ea83de9b99b5c7e33a7c3`、最终交付 `53f322d7e01f73ce03e99b87a579f285ecdb295e`，合并基线 `0ef30a1cba5d50007769dd22308a1f589c84a791`。

C4 正式目录 `server-run/c4/e13-B3-C4-A05-retry025-20261119T135018Z`：外层 FAILED、内层 TIMED_OUT，超时 0.25 秒；超时确认、源码未变、构建客户端不存在、准确验证容器已停止、候选未成功均为 true。结论仅覆盖检查时刻相关 Docker 构建客户端和准确验证容器，不证明或清理 BuildKit 全局缓存。0.01 和 0.1 秒两次校准因构建日志为空未通过证据门禁，原始失败证据保留。

C7 两任务身份、目录、日志和 artifact 隔离，声明产物大小与 SHA-256 全部匹配；A05 源码未变，结束后无相关进程或容器残留。失败任务 `job-0613401d2e0945348d010a8404836210` / `trace-c7ceb9a183ef47dfae43b3f4a65e6748`，无效 base 为 40 个 0，构建前失败，exit 1、FAILED、COMMAND_FAILED。正常任务 `job-cf3d6d61b2994633bc44709d0a72149d` / `trace-f062febeb68046eba1c9d78aa744c288`，exit 0、SUCCEEDED，五阶段完成，175 个 artifact。

H3 是教师 tiny-AES 项目，不是 A/B 实际交换项目；ZIP SHA-256 `d9818c5f34d6ff5b6016222dabd7f56daca09ceaa5f525be214e146e3d485435`，base `dc8099306d7023b7337328d718149973e7b17978`，target `5640bb69a01e64559207e9f74d15a9ae71a4d0f3`。任务 `job-ac4a8b321bfa4821ad49dfe74eecc70b` / `trace-66ad487faad94b9bade775cdc73672f7` exit 0；初始 finding 为 `MISSING helper.o -> extra.h`，最终 remaining findings 0，source unchanged。教师 ZIP、input 源码副本和嵌套 .git 不归档；保留计划、身份、正式 manifest 和阶段产物。

A05 实际交换项目由 241880106 提供，来源提交 `4f39fc3bac39087c666306e3523cfd497fe3dcd9`，P0 `a780dc5679ee7e96cb810a078a1b424c16f87ad0`，base `6b9deff53f8fcf6183204850ac6a9dddb22f1189`，target `90646db8b8ad932da1a959d152942f987aaffff2`。bundle 完整、fsck 通过、base 是 target 祖先，恢复后 target 正确且工作区干净。A 侧自检仅为输入说明，尚未收到 A 组对 B3 返回结果的正式签收。

服务器 E13 unittest 42 项、E13E14 5 项、官方服务容器 E11/E12 54 项均通过且退出码 0；宿主 Python 3.10.12，容器 Python 3.13.14。宿主直接运行 E11/E12 有 6 个 `BaseException.add_note` 版本兼容性错误，原日志保留；官方容器回归为正式结果。runtime log scan：721 个文本文件、0 hits、0 errors、退出码 0。服务器结束时 A05 仍在 target 且干净，外层工作区干净，无运行容器。

已有 CI 针对代码提交 6876b98，运行于正式证据归档提交之前：[E13 B3 local contracts](https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/44479201626)、[E11-E12 integration](https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/44479201328)、[E8-E10 teaching validation](https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/44479201315)。归档提交 CI 尚未知。

归档包含 24 个被原始证据内 `.gitignore` 忽略的构建产物；人工审核后纳入版本控制时须明确强制添加这些文件，并按 manifest 复核完整集合。
