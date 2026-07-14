# earn10m

一个公开记录 OPC（一人公司）经营过程的 Next.js 数据站。网站从飞书多维表格读取日志、财务、业务线和内容发布四类数据；同步与发布默认分离，任何不完整或不可信的导出都不能覆盖正式数据。

## 本地开发

要求：Node.js 20+、Python 3.11+。只有执行真实飞书同步时才需要已登录的 `lark-cli`。

```bash
npm install
npm test
npm run lint
npm run build
npm run dev
```

## 安全同步闭环

```text
lark-cli --format json
        │
        ▼
src/data/.feishu-candidate.*        ← 同文件系统临时目录
        │
        ├─ 空标题/正文日志隔离为草稿，不进入公开快照
        ├─ 严格 JSON
        ├─ 固定四文件与公开字段白名单
        ├─ fields / rows / record_id 对齐
        ├─ has_more=false（拒绝不完整分页）
        └─ 日期、月份、金额、唯一键等最小业务不变量
        │ 全部通过
        ▼
目录原子交换 ───────────────► src/data/feishu
        │
        └──────────────────► src/data/.feishu-last-good
```

macOS 使用 `renameatx_np(RENAME_SWAP)`，Linux 使用 `renameat2(RENAME_EXCHANGE)`。候选、正式数据和恢复快照必须位于同一文件系统；平台不支持安全交换时脚本会失败关闭，不做非原子降级。

### 常用命令

```bash
# 拉取、验证并更新本地正式数据；不会 commit 或 push
npm run sync

# 直接完成安全同步后构建
npm run sync:build

# 从 last-good 恢复正式数据，不回退代码
npm run sync:restore

# 只有人工审查 diff 后才使用；会 commit 并 push 数据目录
npm run publish:data
```

`npm run sync` 和 `npm run sync:build` 会访问真实飞书。测试只使用离线 fake CLI 与 fixtures，不会触发网络、提交或发布。

### 失败语义

- Markdown、空文件、截断 JSON、错误顶层类型或 CLI 错误：正式目录与 last-good 保持字节级不变。
- 目录交换后的校验、hash 或持久化故障：自动交换回旧 live 并返回失败；安装阶段失败会保留权限收紧的候选目录作为人工恢复证据，初检前失败的无效候选仍会清理。
- 任一文件缺失、字段白名单变化、行列错位、重复记录 ID 或 `has_more=true`：拒绝切换。
- 日志标题或正文为空：候选阶段隔离为草稿，不生成公开列表或详情路由。
- `npm run build` 会先自动执行同一数据门禁，避免“页面构建成功”掩盖损坏数据。
- 当前正式目录本身已损坏：保留已有有效 last-good；如果没有，则只从本轮已验证候选初始化恢复点，绝不把损坏数据存成 last-good。
- 正式目录已验证：成功切换后将旧 live 保存为 last-good。首次可信同步时 last-good 只是 bootstrap，并不代表存在更早的可信版本。
- 恢复前会把当前有效 live 保存到 `.feishu-pre-restore`，避免恢复动作不可撤销。
- HUP/INT/TERM 会停止父子任务并在唯一 EXIT 清理中释放锁；若信号恰好命中目录交换临界区，live 仍是切换前或已验证候选之一，但“本次是否已提交”的精确结果仍待临界区故障注入与持久 run manifest 闭环。

### 配置

| 环境变量 | 默认值 | 用途 |
| --- | --- | --- |
| `FEISHU_BASE_TOKEN` | 当前公开数据 Base | 指定数据源 Base |
| `LARK_CLI_BIN` | `lark-cli` | 指定 CLI 路径；离线测试注入 fake CLI |
| `PYTHON_BIN` | `python3` | 指定校验器解释器 |
| `FEISHU_DATA_PARENT` | `src/data` | 候选目录所在父目录 |
| `FEISHU_DATA_DIR` | `src/data/feishu` | 正式数据目录 |
| `FEISHU_LAST_GOOD_DIR` | `src/data/.feishu-last-good` | 本地恢复快照 |
| `FEISHU_PRE_RESTORE_DIR` | `src/data/.feishu-pre-restore` | 恢复前的 rescue 快照 |
| `EARN10M_LOCK_DIR` | `var/locks/data-sync.lock` | LaunchAgent 与交互命令共用的固定锁；子进程还校验真实父 PID |

表 ID 仍作为版本化的数据契约保存在 `scripts/sync-feishu.sh`；变更表或公开字段时必须同步更新校验规则和 fixtures。

## 离线回归测试

```bash
npm run test:sync
```

当前 13 个测试覆盖：

- Markdown 冒充 JSON；
- 空文件；
- 截断 JSON；
- 错误顶层类型；
- 成功候选的目录原子切换；
- 上一份正式数据进入 last-good；
- last-good 恢复；
- 恢复前 rescue；
- 空白日志草稿隔离；
- 字段白名单、分页和重复 ID；
- post-switch 故障自动回滚；
- Shell 安装阶段失败保留候选证据；
- 共享锁拒绝并发任务；
- 无 PID/死 PID 锁失败关闭且不自动清理；
- TERM/HUP/INT 明确停止任务，不会先释放锁再继续同步或发布；
- fake `lark-cli` 的四次调用都显式包含 `--format json`。

上面的若干条是同一测试中的参数化失败样例。

### 锁恢复手册

固定锁故意不会自动清理死 PID 或无 PID 状态，以免旧任务尚在切换数据时被新任务抢占。遇到退出码 75 时：

1. 查看 `var/locks/data-sync.lock/pid`，并用 `ps -p <PID> -o pid=,ppid=,etime=,command=` 确认任务是否仍在运行。
2. 同时确认 LaunchAgent 与交互终端都没有同步、恢复或构建任务。
3. 只有确认没有数据任务后，人工删除整个 `var/locks/data-sync.lock`，再执行一次 `npm run sync`。
4. 若存在 `.feishu-candidate.*`，先运行校验器并比较 live/last-good，再决定恢复或删除；不要直接把候选目录改名为正式目录。

## 目录说明

```text
src/app/                         Next.js 页面
src/data/finance.ts              飞书数据读取与经营指标计算
src/data/feishu/                 当前正式公开数据
scripts/sync-feishu.sh           隔离导出入口
scripts/feishu_data_sync.py      Schema、业务不变量、原子切换与恢复
scripts/auto-deploy.sh           同步/人工发布守卫
tests/fixtures/feishu-sync/      完全离线的成功与失败样例
tests/test_feishu_data_sync.py   数据安全回归测试
docs/PRD.md                      产品需求与验收口径
docs/LOOP.md                     持续核查、交付与复盘闭环
```

## 发布纪律

1. 先运行 `npm test && npm run lint && npm run build`。
2. 运行 `npm run sync` 后人工查看 `git diff -- src/data/feishu/`。
3. 检查公开字段、金额口径、隐私和数据新鲜度。
4. 确认工作区没有数据目录以外的改动后，才运行 `npm run publish:data`。

当前机器上的小时 LaunchAgent 仍调用默认同步（不带 `--publish`）；暂停、恢复或修改它属于运行态操作，需要在受控窗口单独处理。Telegram Bot 必须在允许用户配置迁移后才能重启。

发布脚本仅精确暂存 `src/data/feishu/`，不会执行 `git add -A`，也不会直接调用 Vercel 生产部署；后续部署由仓库 CI/Vercel Git 集成负责。
