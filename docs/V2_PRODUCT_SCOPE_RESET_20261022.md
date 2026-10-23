# AI 3D Game Image Harness — V2.0 精简开发与交付方案

> 执行基线：2026-10-22，`feat/v0.14-isolated-radio-editor-proof` / Draft PR #20。
>
> **本文件调整的是产品范围和交付方式，不是重写软件版本或声称 Steam 商业验收通过。**
> 代码开发版本仍是 v0.14-dev。真实证据不足时一律标为 BLOCKED 或 NOT_VERIFIED。

## 1. 已确认的核心决定

**产品定位**：单人 + Codex + ChatGPT 订阅驱动的 AI 游戏图像制作工具。优先服务《Second Life Workshop》的 KNIFE_001；先把真实素材任务做得稳定、可复用，再扩展游戏资产类型。

唯一常用操作流程：

```
已有/经批准的 Master、asset.toml、edit.toml
   ↓
produce run（复用既有生产执行器）
   ↓
Codex 原生 ImageGen → SHA 绑定的原生 PNG/Receipt
   ↓
按需严格 Mask、ROI / 特定材质后处理（不伪装为模型直接生成）
   ↓
有限次数的真实视觉 QA 和必要修复
   ↓
独立 production-audit 验证
   ↓
技术候选 PNG + 状态/失败原因
```

用户只需要一个任务入口、一个结果状态、一个可追溯结果。其余工具留作维护及专业排错，**不再要求用户理解每个 Receipt、审计脚本和 Git 分支**。

## 2. 冻结 v1.0 可用版范围

| 纳入 v1.0 技术可用版 | 本阶段明确不做 |
| --- | --- |
| 一个 `produce run` 创建/恢复单个任务；`produce status` 查状态 | 第二套运行状态机、第二个图像模型、本地 GPU 推理或收费 Images API |
| 沿用已有原生 Codex ImageGen、Master/Mask/ROI、严格像素保护 | 通用 PBR/3D 网格自动重建、Unity 游戏测试平台重造 |
| 一项真正被 SHA 独立审计的非商业技术候选素材 | 以单元测试代替模型/视觉验证、合成 PNG 冒充原生 PNG |
| 按需启用已证明有效的材质专用后处理 | 在 KNIFE_001 前无限扩展 LAMP/RADIO 细分材质 |
| 限额修复、不可重放的证据、原始文件不被覆盖 | 无限制 Host 重试、自动覆盖/提升 Master |
| 机器视觉 QA 与技术审计分离；状态明确区分质量与权益 | 将机器 PASS 等同人工美术、版权或 Steam 批准 |
| 导出带明确技术范围的 PNG/Receipt；可独立 Unity 导入查看 | 将隔离 2D 贴图测试冒充完整 3D 游戏验收 |

**不可削减的安全底线**：获批原始 Master 不覆盖；未提交文件、原生 PNG、Mask 和失败记录不删；没有真实原生 ImageGen/Receipt/QA 就不能显示技术 PASS；未通过来源权利与人工签收则不能显示商业 READY。

## 3. 单一用户操作入口

```bash
# 一个已有且位于同一工作区的 asset.toml + edit.toml（批准 Master/Mask 的 SHA 固定在合同中）
./bin/ai-3dgame-image-harness produce run \
  --workspace-root /absolute/private/asset-workspace \
  --asset asset.toml --edit edit.toml

# 被安全中断时显式恢复（不得自动覆盖/重做模糊的宿主步骤）
./bin/ai-3dgame-image-harness produce run \
  --workspace-root /absolute/private/asset-workspace \
  --asset asset.toml --edit edit.toml --resume

# 只读查询；若 Run 为 ACCEPTED，自动独立重验 production-audit
./bin/ai-3dgame-image-harness produce status \
  --run /absolute/private/asset-workspace/run.json
```

结果统一输出 `run_state`、`technical_audit`、`output_png`、`output_sha256`、`machine_visual_qa` 和阻塞原因。

- 退出码 **0**：真实技术生产审计 PASS，仍明确标记人工/权利/Unity 游戏/Steam 未验。
- 退出码 **3**：已达到本轮限额、待用户显式继续；不能当成完成。
- 退出码 **2**：BLOCKED 或审计错误；不提供可信导出 PNG。
- 这个新入口仅薄封装原有 `production_autopilot.drive`、`production_audit.audit_run`，**不写新状态机**。
- 历史 `autopilot`、`precision-compose`、`batch` 等命令全部保留向后兼容。

## 4. 已核实基线（不将研究样本当商业合格样本）

| 真实证据 | 截至 2026-10-22 状态 |
| --- | --- |
| RADIO `smooth_nonmetallic_enamel_face_v1` | 真实 Codex 原生生成、Mask、材质确定性后处理、29/29 机器 QA、独立 production-audit PASS |
| RADIO 交付图 SHA-256 | `a8f6c83d5759cdc17681ec04ee6034b1a3dd46748718b3322d48ad0f44c9d83c` |
| Unity 6.6.3f1 独立 Editor | 导入、正确朝向、实际渲染对源像素 MAE 2.56475/255，PASS |
| Unity v002 非开发 macOS Player | 已实际启动、OSXPlayer/Metal，3840×2160 原生截图 SHA `990910e07b86a59ba710de690b9fb5f1601a7a9a67e301d64580bc3da2504574` |
| Player 4K 帧时间 | 100 帧，中位 104.84ms、p95 116.73ms；**不能据此声明 60fps** |
| LAMP 拉丝钢 | 细纹理未通过可信艺术质量验收 |
| KNIFE_001 | 当前权威 Master/Blender/Unity 来源尚未完成正式对账和真实精确编辑 |
| 12/30/60 权利完整商业批次 | 尚未完成，不能计入 v1.0 技术完成的进度 |

相关公共 PR：[严格原生审计 #18](https://github.com/qiguang0916/ai-3dgame-image-harness/pull/18)、[RADIO 完整技术审计 #19](https://github.com/qiguang0916/ai-3dgame-image-harness/pull/19)、[Unity Editor 真实渲染 #20](https://github.com/qiguang0916/ai-3dgame-image-harness/pull/20)。截至本方案建立时均为 Draft、尚未合并 `main`。

## 5. 重新排序：只走一条开发主线

### P0 — 收敛现有分支为可安装技术基线

1. 使用目前最末的 `feat/v0.14-isolated-radio-editor-proof` 作为**唯一后续研发 Head**；PR #16–#20 为历史链条，不再为每个小修复建立新 PR。
2. 保留 308+ 项现有测试与现有真实审计，整合用户文档和 `produce` 唯一入口；删除需求范围中的重复流程，而不是删掉审计证据。
3. 审核 PR 链条的依赖、未合并改动与 Mac 原工作树；确认安全备份/对账前 **绝不 merge main、reset、clean、强制推送或改写历史**。
4. 不把更新的 README、工作区配置或代码测试当作新的模型成功样本。

**退出条件**：一个从已知真实 Run 只读查询可重新验算 PASS；负面测试证明伪造、篡改和非终态都不能输出 PASS；GitHub CI 与干净检出一致。

### P1 — KNIFE_001 真实游戏素材试点（最优先新美术任务）

1. 先核实并固定 KNIFE_001 **唯一**权威 Master（用户指定 v030E 作为追溯锚点），与最终参考、Blender 源及 Unity 资产的对应关系；不擅自提升候选。
2. 明确一个微小、可审核的局部修改，冻结几何轮廓、锻钢与红花梨木柄等保护规则，定义可检查的技术和视觉硬门禁。
3. 在新私有工作区调用真实 `produce`；如果材质或身份不达标就维持 BLOCKED，并提供失败点，而不是反复无限重试。
4. 通过后输出可导入 Unity 的**候选**素材，先在隔离 Unity 工程验证；正式游戏集成需要单独审查。

**退出条件**：有一轮真实 KNIFE 生成/修复及可复核来源、Mask、机器 QA、审计、失败或成功的如实记录；得到正当审核后才计为技术候选。**不承诺 AI 一定首次生成满足审美。**

### P2 — 可用版交付

- 对外一个简短 README、一个命令入口、一个真实示例、错误状态说明；支持简单安装和恢复。
- 生成 PNG + 机器技术证据与权利/艺术未验的独立状态，不要求用户手工串接几十条命令。
- 不破坏现有已验证的 RADIO 和 v0.9–v0.14 契约；全量回归及真实样本仍可复核。

**技术版验收**：独立环境可以执行一条明确的真实单任务、失败可解释、不可重试无证据的运行、可保留并导出技术候选。可用版不等于 Steam 上架产品。

### P3 — v1.x 商业增强（从 v1.0 技术可用版剥离）

在资源充足且权利证据真实的前提下，再推进 LAMP 专业拉丝纹理、30/60 批次可靠性、游戏中真实 3D 材质/Player 性能、Steam 商店图及人工版权审核。它们继续是**各自的发布门禁**，但不冻结非商业技术工具的可用版交付。

## 6. 衡量进度的方式

不再以“82%”“单元测试 308→318 个”“PR 数量”“报告数量”衡量进展。

每项任务只统计五个实际状态：

1. **RUN**：是否真正执行 Codex Host，原生图片/事件是否留存？
2. **QUALITY**：指定目标与保护区是否通过独立量化/机器视觉？人工视觉结论单独记录。
3. **AUDIT**：是否由生产审计重新证明各 PNG/Receipt/Mask/来源绑定？
4. **USABLE**：是否能通过单一入口输出并在需要的 Unity 场景正确查看？
5. **RELEASE**：最终人工美术、权益和 Steam 发布是否有可验证的外部凭证？

每个维度都可以分别为 PASS、BLOCKED、NOT_VERIFIED，不再把技术试点自动计入商业批次。

## 7. 保护措施与禁止事项

- 不修改正式 `Second Life Workshop` 游戏工程；Unity 验证只使用单独创建的隔离项目。
- 不删除或覆盖任何脏工作树、图片/Mask/Receipt/Host transcript、已冻结 Master 和失败 Run。
- 原始 Mac 根工作树仍需安全对账；连接权限已有 `dc_bridge`，不再误称启动 Player 必须恢复 Desktop Commander。
- 不把 `open -a` 放进桥接白名单；长驻 Player 管理可单独在获授权接口实现，但**不属于核心图像 v1.0 的准入条件**。
- 不引入商业专有或未知许可参考作为可分发素材，不公开用户私有图像和构建产物。
- 不新增第二套批处理框架、测试框架或美术引擎；第一选择永远是复用已证实的代码。
