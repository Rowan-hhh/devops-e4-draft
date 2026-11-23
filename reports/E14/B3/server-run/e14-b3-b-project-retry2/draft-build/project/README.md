# E12 B 组维护项目

从本组 E7 使用的 fixtures/draft 派生，完整来源见 SOURCE.md。
本项目不是外部生产项目，未复制 integration-sample。

本版本将原 greeting 程序演进为可配置数值输出程序：main.c 读取
config.h 的 VALUE，helper.c 实际执行 printf 并返回成功或失败。
main.o 正确声明 main.c/config.h，helper.o 正确声明 helper.c。

构建：make clean，然后 make app。运行：./app。
stdout 严格为 1\n（一个换行），stderr 为空，退出码为 0。
make clean 后无构建产物。CFLAGS = -O0。

Dockerfile.broken 故意不安装 make；其预期失败必须由后续服务器实际验证。
P0 导入时保留的 Dockerfile.reference 仅为原始来源，不是本项目候选。
本地 C 构建成功不等于服务器 DRAFT 成功。A 组报告尚未收到。
