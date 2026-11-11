# ADR：E11 B4 验收基线与证据边界

## 决策

B4 以 `e11-e12-integration` 的 `3e96221c3ab3d1c55dffedb6d5ee23f020c3af8e` 作为唯一集成基线，保留 B1、B2、B3 的原始报告和日志，不从旧 `main` 重放上游贡献。

## 原因

B4 的职责是集成、完整运行和验收，不应覆盖上游成员的实现或重写原始证据。镜像构建必须在 GitHub Actions 的 Linux/Docker 环境中完成；本地只报告真实执行过的 Python 合约测试。

## 验收门槛

只有在 E11-E12 workflow 的测试、prepare、e11-a、e11-b、e12 全部成功，并且 PR Checks 通过后，才把 `acceptance.json` 状态更新为 `PASS`。

