# A05 实际项目交接包（E13，A → B）

供 B 组用 DRAFT/MDFixer 对 A 组项目做交叉测试（C1、C3、C4、C5、C7 等）。
不是教师样例；来源、提交与预期见 `MANIFEST.json`，项目内另有 `SOURCE.md`、`README.md`。

## 文件

| 文件 | 用途 |
| --- | --- |
| `a05-project.bundle` | 项目完整历史（分支 `main`，P0→base→target 线性） |
| `request-e12.json` | 正常 E12 五阶段请求 |
| `request-e11-a.json` | A 侧全量/增量请求（同一 base/target） |
| `candidate.Dockerfile` | DRAFT 修复候选（在 `Dockerfile.broken` 基础上只增加安装编译工具的 RUN，走清华镜像） |
| `MANIFEST.json` | 提供者、提交、祖先关系、预期结果、A 侧自检记录 |
| `SHA256SUMS` | 以上文件的 SHA-256 |

- base：`6b9deff53f8fcf6183204850ac6a9dddb22f1189`
- target：`90646db8b8ad932da1a959d152942f987aaffff2`
- 预期输出：`1`（`config.h` 改为 `VALUE 2` 后为 `2`）
- 预期检测：base 无发现；target 仅 `MISSING helper.o→clamp.h`；修复为 `HELPER_DEPS` 追加 `clamp.h`（macro 风格）

## 恢复（在 B 组仓库根目录执行）

```bash
PKG=<交接包所在目录的路径>
(cd "$PKG" && sha256sum -c SHA256SUMS)
git bundle verify "$PKG/a05-project.bundle"
git clone "$PKG/a05-project.bundle" data/a05-project
git -C data/a05-project rev-parse 6b9deff53f8fcf6183204850ac6a9dddb22f1189 90646db8b8ad932da1a959d152942f987aaffff2
git -C data/a05-project merge-base --is-ancestor 6b9deff53f8fcf6183204850ac6a9dddb22f1189 90646db8b8ad932da1a959d152942f987aaffff2 && echo BASE_IS_ANCESTOR
cp "$PKG/candidate.Dockerfile" data/a05-candidate.Dockerfile
cp "$PKG/request-e12.json" data/a05-e12.json
cp "$PKG/request-e11-a.json" data/a05-e11-a.json
```

请求中的路径为 `/course/data/a05-project` 与 `/course/data/a05-candidate.Dockerfile`，`run_e11e12.py` 会把仓库根目录挂载为 `/course`。
按上面位置放置即可不改请求；若放在别处，只改 `repo` 和 `candidate` 两个字段，并在测试记录中写明。

```bash
python3 run_e11e12.py run --request data/a05-e12.json --out work/<全新目录>
```

## 故障注入提示（B 侧 C4/C7）

- C4：复制 `request-e12.json`，只把 `build_timeout` 改为 `0.01`，写入新请求和新输出目录；预期外层 `FAILED/DRAFT_FAILED`、内层 `draft-build/result.json` 为 `TIMED_OUT`，随后用原请求在新目录恢复。
- C7：复制请求，把 `base` 改为 `0000000000000000000000000000000000000000` 制造失败，再用原请求运行正常任务；两次 job_id/trace_id 与产物须互不混用。

## 约束

- 只交换本目录文件；不含 `.env`、密钥或服务器口令。bundle 恢复后的工作区与 `git log -p --all` 全历史已用 `scan_runtime_logs.py` 扫描，命中 0。
- 不得修改 bundle 内提交来让测试通过；发现缺陷请按 `缺陷Issue与修复PR` 模板回传 A 组。
