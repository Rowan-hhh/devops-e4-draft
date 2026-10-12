# E4 B组分工

## 分工表

| 流程 | B组负责人 | A组对应负责人 | 交互内容 |
|---|---|---|---|
| ① 仓库模板与接口确认 | B3 易容卉：接口与 README 负责人 | A组 BuildChecker 负责人 | 仓库地址、README、目录结构、模板 SHA、构建与验证命令 |
| ② 服务器与镜像构建 | B1 周逸涵：环境与构建负责人 | A组环境负责人 | SSH、Docker 版本、基础镜像 digest、`toolchain.lock`、构建日志 |
| ③ DRAFT 容器与安全 | B2 谢真婷：容器运行与安全负责人 | A组 BuildChecker 负责人 | `docker.sock`、`DOCKER_GID`、资源限制、`.env`、密钥扫描 |
| ④ 组员重跑与最终验收 | B4 史美一：重跑与交付负责人 | A组复核负责人 | 两名组员分别运行 `make all`，比较 SHA、工具版本、测试和冒烟结果 |
| ⑤ 跨组相互检查 | B4 史美一：统筹负责人 | A组交付负责人 | 交换仓库地址，仅按 README 重跑，说明差异或确认一致 |

## 每名成员必须完成

```bash
git clone <本组仓库地址>
git config --local user.name "<学号>"
git config --local user.email "<学号>@localhost"
git rev-parse HEAD
make doctor
make all
```

每名成员应记录所测源码 SHA、成功证据目录、工具版本、测试结果、冒烟结果和密钥扫描结果。

## 仓库

- B组 DRAFT：<https://github.com/Rowan-hhh/devops-e4-draft>
- A组 BuildChecker：<https://github.com/Avaland-Kong/devops-e4-buildchecker>
