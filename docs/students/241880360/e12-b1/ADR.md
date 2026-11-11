# E12 B1：维护项目与独立 DRAFT 入口

## 决策

按已确认课程口径，从 E7 使用的 fixtures/draft 建立独立 E12 B 组维护项目，
不是外部生产项目。真实来源与 P0/P1/P2 完整 SHA 见 reports/E12/B1/project-source.json。
三次提交使用本人身份与实际时间；不调用 prepare.py，不复制 integration-sample，不改写历史。

选择双源演进：main.c 读取 VALUE，helper.c 实际 printf 并返回状态。
P1 依赖声明完整；P2 实际将格式提取到 output_format.h，暂不更新 helper.o 声明。
这是显式记录的课程受控演进，不宣称自然生产缺陷或 A 组已经检测成功。
此方案不需要修改 scan/declarations、pipeline 或公共验证 profile。

新增独立 b1.py，以 run_e11e12.py e12-b1 调用，生产代码不导入 pipeline、lab、server 或检测器。
只验证来源/真实 Git 版本、隔离 target、运行 vendor DRAFT 并记录不变性。
不对整个 .git 做哈希；比较受跟踪文件路径与 SHA-256、HEAD、show-ref、porcelain 状态和本地身份。
Git 读取设置 GIT_OPTIONAL_LOCKS=0。已有输出（包括空目录及符号链接）均拒绝。

旧 prepare_candidate 拒绝相同固定 digest FROM；先用单测复现，再最小兼容修复，
保留 broken 未固定、candidate 固定的旧路径。新增可选 candidate_source 保留默认值，
允许如实记录本次人工准备来源。B1 另作严格结构比较，只允许审核过的系统安装 RUN。

## 归档与恢复

外层继续忽略 data/ 与 work/；完整历史使用 project.bundle，避免 gitlink 与绝对路径依赖。
恢复：验证 project-source.json 中的 bundle SHA-256，git bundle verify，
git clone 到新目录，核验 base/target 与祖先关系，checkout target 并核验源码哈希和干净状态。
详细命令见 reports/E12/B1/README.md。不得在另一机器重建三次提交。

## 当前边界

本轮只完成 B1 项目准备和入口实现。普通 C 构建与 mock 单元测试不是服务器 DRAFT 证据。
当前未运行 Docker，未取得服务器 DRAFT 成功结论，未收到 A 组真实报告。
B2 最终 Patch、B3 API 联调、B4 五阶段验收均未执行。
不生成 handoff、run/、archive-manifest 或个人正式实验报告，等待服务器真实运行。
外层不暂存、不提交、不推送。

## 风险与失败处理

基础镜像平台、Docker 和软件源仍待服务器核验。基础设施失败必须如实保留，使用新目录重试。
失败不得覆盖旧输出或虚构成功；原项目有任何变化则 B1 失败，不自动恢复用户文件。
若项目提交发现问题，停止并人工审核；不得 amend、rebase 或回填提交时间。
