# A05 维护项目：quota-scale

A05 组（A 轨道 BuildChecker/EChecker）为 E13 交叉测试维护的 C/Make 项目，
从本组 E3/E7 的 `fixtures/md-rd` 派生，来源见 SOURCE.md。不是外部生产项目。

## 行为

- `main.c` 读取 `config.h` 的 `VALUE`，调用 `helper.c` 的 `scale()` 后输出。
- `helper.c` 按 `scale.h` 的比例换算（当前 1/1）。
- 构建：`make clean && make app`；运行：`./app`；测试：`make test`。
- 预期：stdout 严格为 `1\n`，退出码 0。`config.h` 改为 `VALUE 2` 后输出 `2`。
- Makefile 用 `HELPER_DEPS` 变量声明 `helper.o` 的依赖（与教师样例、B 组项目的直接写法不同），
  用于检查修复器对变量形式依赖列表的处理。

## 版本计划

| 提交 | 角色 | 依赖检测预期 |
| --- | --- | --- |
| P0 | fixture 原样导入 | 单源文件，MD `main.o→config.h`、RD `main.o→unused.h`（不在流水线适配范围内） |
| P1 | E13 base | 双源文件，依赖声明完整，无 MISSING/REDUNDANT |
| P2 | E13 target | `helper.c` 新增 `clamp.h`，`HELPER_DEPS` 未更新：MISSING `helper.o→clamp.h` |

## DRAFT

`Dockerfile.broken` 故意不安装 make，用于 DRAFT 复现 `MISSING_MAKE`；
修复候选不在本仓库，随交接包单独提供。

## 适配范围

两个 C 源文件（main.c、helper.c）、`config.h`、显式 Make 规则、`CFLAGS = -O0`、输出 `1`。
