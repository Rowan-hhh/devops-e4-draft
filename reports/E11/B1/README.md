# E11 B1 交付记录

- 姓名：周逸涵
- 学号：241880300
- 角色：B 组 B1（公共准备、实验包导入、镜像构建、DRAFT 两轮构建与镜像运行）
- 仓库：`https://github.com/Rowan-hhh/devops-e4-draft`
- 分支：`e11-e12-integration`
- CI：运行 `42748595650`，结果为 `success`
- 个人镜像标签：`course-e11e12:241880300`
- 个人镜像 ID：见 [image-id.txt](image-id.txt)

## DRAFT 构建结果

CI 运行生成的 `draft.json` 与 `draft-build/result.json` 已保留。DRAFT 两轮构建结果为：

1. 第 1 轮退出码为 1，失败分类为 `MISSING_MAKE`。
2. 第 2 轮退出码为 0，镜像运行退出码为 0，实际输出为 `1`。

两轮原始构建日志位于 `draft-build/iter-01/` 和 `draft-build/iter-02/`；验证输出位于 `draft-build/verify.log`。

## CI 证据

- Workflow：[E11-E12 integration](https://github.com/Rowan-hhh/devops-e4-draft/actions/runs/42748595650)
- Artifact：`e11e12-evidence-42748595650`，ID `13731649036`
- Artifact digest：`sha256:9ac6734ef3c824452b21923a85cb118e950d6c807fcd01cb7840720dd924e594`
- 合约测试：10 项通过
- E11 B 全流程：成功

本机未安装 Docker，因此镜像构建和运行证据以 GitHub Actions 的 Ubuntu 24.04 CI 为准；本地合约测试已独立执行并通过。
