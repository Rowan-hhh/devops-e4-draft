# E14 RC Checklist

- [x] B1 正式归档及固定样例验证为 PASS。
- [x] B2 四服务交接验证为 PASS。
- [x] 受控故障产生 FAILED 记录，失败日志保留。
- [x] 恢复使用新的 job/trace，五阶段运行成功，最终 `MISSING=0`。
- [x] 输入项目 HEAD、候选 Dockerfile 和 fixed report 前后 SHA 一致。
- [x] 运行日志秘密扫描为 0 hits、0 errors、exit 0。
- [x] 已记录已知问题和回退步骤。
- [ ] 本分支 PR CI 全部通过。
- [ ] 组长审核并合并到 `main`。
- [ ] 维护者授权后创建 `v0.9-rc`；不得覆盖已有标签。
