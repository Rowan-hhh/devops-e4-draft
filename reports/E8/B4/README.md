# E8 B4 旧报告拒绝与源文件保护

负责人：周逸涵，2418880300，B组/B轨，本阶段角色 E8 B4（测试与复核）。

## 分支与输入

- 仓库：https://github.com/Rowan-hhh/devops-e4-draft.git
- 独立角色分支：`e8-zyh-b4`
- 角色贡献基线：`main`，外层源码提交 `7a828315f0e9c8057d031b2f45b5af7bfce2849b`
- 本次本地证据目录：`work/e8-B-20261105-zyh-b4/`（按约定不提交）

## 验证结果

使用 E8 B 轨道样例运行 `lab.py e8 --track B`，固定报告的样例内部 HEAD 为 `1107ca7e2eb4fb1fa46c0527d61ee874ce159ac7`，发现集合为：

- `MISSING main.o/config.h`
- `REDUNDANT main.o/unused.h`

候选 Patch 只把 `config.h` 加入 `main.o` 声明，未修改编译 recipe，也未删除冗余声明。伪造旧报告的 `commit` 后，程序生成：

```json
{"error":"STALE_REPORT"}
```

样例项目工作区保持干净，原始 Makefile 字节没有被旧报告请求改变。

## 个人贡献

在 `labs/e8e10/test_profile.py` 新增 `StudentE8B4.test_stale_report_rejected_without_changing_source`，独立断言：

1. 旧报告被拒绝为 `STALE_REPORT`；
2. Makefile 拒绝前后逐字节相同；
3. 样例 Git 工作区没有未提交修改。

本分支只包含 E8 B4 的测试、报告和证据说明；E9 B3 位于独立分支 `e9-zyh-b3`，个人完整 E8—E10 运行位于 `student/2418880300/e8-e10`。
