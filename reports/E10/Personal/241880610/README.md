# E10 B 轨个人完整复跑

执行人：谢真婷（241880610）。

- 外层源码：`30fa33138b5755ddccc91ebdb6fe1b1c2c509238`
- 同步的最新 main：`5d2f02424cc0ba2ba2ec3dfe06585d0e28be6bf1`
- Docker OUT：`work/e10-B-personal-241880610-20261108-docker`
- 镜像 ID：`sha256:9382c81129db71d4d455bee0fbe36ffc136e6113984ba17f29a5f17a99b98a8e`
- 新样例 HEAD：`fca7619d276b7e9e7d925d3d880bd3a629f27e46`

错误测试预期、正确候选和无效 Patch 三个场景均通过；错误场景拒绝并保持源项目不变，正确候选五项验证通过后接受。最终 `gate.json` 为 `passed=true`，`results.csv` 三行全部通过；BuildChecker 重检为 `SUCCEEDED`，`MISSING` 数量为 0，保留预期 `REDUNDANT main.o -> unused.h`。

完整单元测试为 `58 passed`，日志位于 `out/unit-tests-correct3/test.log`。全部新证据已归档在本目录的 `out/`。
