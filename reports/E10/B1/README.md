# E10 B1 交接归档

B1 负责环境、独立样例和构建交接，接收方为 B3。

- 基线：`7a7ff8de16930742201ad59f07b22e96380fcb15`
- 实现及执行提交：`cea139b3f60ffa04cd318009292d53d890029b40`
- 内部样例 HEAD：`93ea08243be717cfe00502120ddebf2d090bdff7`
- Linux/amd64（运行环境记录为 x86_64）镜像 ID：`sha256:94a15175783fe4f37f17f1ae1208edfbdd2524206304e1b1ce56295f27823c40`

原始 direct project 在隔离构建前后输入哈希一致，Git 干净，无 app 或对象文件污染。隔离副本的 make clean、make app 和程序运行均通过，输出为 `1`，日志见 build/。17 项测试通过，退出码为 0；已有输出目录拒绝覆盖，记录见 output-exists-check.log。

project/ 仅保存七个普通输入文件，不含内部 .git 或构建产物。project.bundle 保存完整内部历史，验证结果见 project-bundle-verify.log。B3 应恢复 bundle，以保留准确的内部样例 HEAD，而非在普通文件副本中重新初始化 Git：

```bash
git clone reports/E10/B1/project.bundle <新目录>
git -C <新目录> rev-parse HEAD
```

恢复后的 HEAD 应为上述内部样例提交。B1 未生成 fixed-md-report.json、candidate.patch 或 source-before.Makefile；由 B3 在干净样例上继续生成。

241880360-handoff.json 按原始字节归档。archive-manifest.json 记录本目录其余所有归档文件（含 README 和 bundle）的 SHA-256；不包含 manifest 自身，避免自引用。
