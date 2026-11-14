# E12 B1：维护项目、精确候选与服务器证据

从本组 E7 使用的 fixtures/draft 派生独立 E12 B 组维护项目，明确为课程 fixture 派生，
不是外部生产项目。来源提交、P0/P1/P2 实际身份与时间、base/target 和完整历史见
reports/E12/B1/project-source.json、project.bundle。未运行 prepare.py 生成维护历史。

采用双源设计：main.c 读取 config.h 的 VALUE，helper.c 实际 printf 并返回状态。
P1 声明完整；P2 将格式提取到 output_format.h 并实际使用，暂不补 helper.o 声明。
这是可追溯的受控依赖演进，无需扩展已有双对象 profile，也不冒称 A 组检测结论。

B1 独立入口 run_e11e12.py e12-b1 只校验来源、身份、完整 SHA、祖先关系和干净状态，
隔离 target 后调用 vendor DRAFT。生产入口不导入 pipeline、lab、server 或检测器。
原项目不变性比较受跟踪文件路径与哈希、HEAD、refs、状态和身份，不对整个 .git 做哈希。
取得 before 后的副作用受 try/finally 保护，先在内存比较 after，再尽力写证据；
已有输出目录拒绝覆盖，失败和异常不得伪造成功。

候选与 broken 的固定 FROM/digest、WORKDIR、COPY、RUN make app、CMD 严格一致，
仅允许唯一精确安装 RUN。相同固定 digest 与旧 vendor 未固定来源兼容的最小修复已保留，
B1 自身继续精确比较完整指令，不接受任意 RUN 或拼接额外 shell 命令。

服务器环境首次访问 Docker Hub 超时，Docker CLI 使用同 digest 的 DaoCloud 地址后成功。
bundle 恢复不携带本地配置，首次调用因此缺少 Git identity，在 DRAFT 前拒绝；补齐后才继续。
旧候选第二轮官方 Debian 源过慢，600 秒后 TIMED_OUT，原项目未变，失败证据保留。
采用固定 TUNA HTTPS Debian/Security 源、IPv4、3 次重试是网络可靠性修正；
只安装 gcc/make/libc6-dev，并清理 apt 列表，不变更程序、构建和输出语义。

最终服务器 DRAFT SUCCEEDED：第一轮 MISSING_MAKE，第二轮构建及镜像运行退出 0，
输出为 1 加一个换行，原项目未变。正式执行代码提交为
8cd9224f32f73594c1c921cd4553cedb3760b55f，证据见 reports/E12/B1/run/success/。
原生本地检查、mock 测试、服务器失败和最终成功分别记录，不相互替代。

外层继续忽略 data/、work/，通过完整 bundle 和相对路径交接；
run 传输仅排除 target-project/.git，原始字节保持，manifest 排除自身。
来源清单更新为执行后归档状态，重跑应使用执行提交中的原运行前清单，不能改写归档来绕过前置校验。

交接对象为 A 组及后续 B2。A 组报告尚未收到；本任务不生成 A 组 incremental-check、
B2 最终 Patch、repair/recheck，不执行 B3 API 或 B4 五阶段验收。
本次仅整理真实证据和文档，不运行 Docker，不暂存、提交或推送。
