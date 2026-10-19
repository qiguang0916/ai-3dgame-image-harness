# ai-3dgame-image-harness v0.10 → v1.0 完整开发计划与 Codex 任务分解

> 状态：PLANNED，除明确标注“现有能力”的项目外，本文所有任务尚未实施。
> 日期：2026-10-19。代码基线：v0.10.0-dev / 7a7e35e。
> 配套：V1_PRODUCT_AND_ARCHITECTURE.md、V1_ACCEPTANCE_AND_TEST_MATRIX.md。
> 目标：保证一人 + AI 能低成本、可重复、可审计地向 Steam 游戏交付真实高质量图像素材；实现可自主执行的工程步骤，而非伪造商业或法律审核。

## 1. 全局工作规则

1. **保留仓库**：/Users/qiguang/ai-3dgame-image-harness；远端 qiguang0916/ai-3dgame-image-harness。不得重建项目，不得动无关 Unity 主工作树。
2. **继承当前能力**：不要重新实现 ImageGen 生成后端、v0.9 的 Receipt/Visual QA/Repair/Resume、v0.10 的 batch、Steam 门禁和 Unity 原图暂存。
3. **规划文档不等于实现**：每个子任务完成标准是代码+测试+真实证据；不能只提交 README/设计草图。
4. **独立分支**：建议每个版本使用 feat/v011-asset-contract 等独立分支，以 v0.10 当前受测分支为起点，按仓库审核流程提交 PR；不得强推 main 或擅自合并。
5. **人工审批点**：Approved Master、来源版权许可、最终美术及 Steam 内容问卷不得由模型自行宣称批准。
6. **成本边界**：默认依赖 ChatGPT 登录的 Codex 原生 image_gen，任何新付费 API/第三方服务/本地大模型部署需先批准；按 max-jobs、max-actions、repair budget 限流，不能无限循环。
7. **证据边界**：真实 PNG、事件原文、私人参考素材、Unity build 和截图留在忽略的私有目录；公共仓库仅提交程序、测试、去标识化摘要和可公开文档。
8. **阻断优先**：任何失败或未知 = BLOCKED/NOT_VERIFIABLE，禁止用手填 PASS、构造测试图片、复制历史截图来满足生产验收。
9. **无人值守只限技术工作**：允许任务排队、定界重试、断点恢复；若权利/结构/未知 QA 问题不能验证，停在审核队列，不继续生成。
10. **每次合格提交最小证据**：git diff --check、项目 validator、unittest、demo_e2e、真实运行记录（仅在该任务要求时）、未破坏既有接口的证明和链接到 commit 的验收表。

## 2. 版本计划总表

| 版本 | 核心问题 | 核心交付物 | 退出门禁 |
|---|---|---|---|
| v0.10.1 | 可靠性基线和已知缺陷 | 崩溃恢复/任务隔离/基线测量 | 旧178测试无回退；崩溃注入不误重放 |
| v0.11 | 美术需求能否变成强约束 | AssetSpec v2 + Reference Authority + Style Kit | 原有 manifest 兼容；冲突/缺失拒绝；多品类规格通过 |
| v0.12 | 图片能否精确修改并被可靠审查 | 区域掩码、客观 QA、人工审查协议 | 严格保留区无误改；真实 A/B 漂移统计、假通过评测 |
| v0.13 | 能否稳定做规模化真实生产 | Benchmark + Budget + Batch Recovery + Dashboard CLI | 真实任务按门槛完成；中断恢复无重复生成 |
| v0.14 | 能否用于真正 Unity 游戏 | Staging manifest v2 + isolated Unity Import Adapter + Player compare | 实际导入、实际截图、质量/性能无阻断 |
| v0.15 | 能否进入商用发布审查 | SPDX/rights lineage、Steam 图片合规、构建证据聚合 | 缺权利/游戏/申报即 BLOCKED；报告可复核 |
| v1.0 RC | 跨品类、跨分支与游戏的交付验收 | 冻结 API、回归矩阵、签名索引、Release Candidate | 通过全部 V1_ACCEPTANCE_AND_TEST_MATRIX.md 发布门禁 |

完成顺序不可颠倒：v0.11 的契约数据支撑 v0.12 QA；v0.12 QA 支撑 v0.13 真实生产；可靠真实产物才可进入 v0.14 Unity；v0.15-v1.0 是完整交付门禁而不是再造模型。

## 3. v0.10.1 — 当前开发版稳定（P0）

**任务 A01 — 固定现有源代码基线**
- 核对 v0.10 最新分支、全部 tracked/ignored、Git status、README/AGENTS、各测试脚本；保存 HEAD 与依赖版本（Python/Codex/Unity）。现有私有证据禁止搬入公共仓库。
- 产物：docs/V101_BASELINE.md（基线、环境、已知缺陷、实际 Test Command）。
- 验收：不修改用户游戏工作树；validator/unittest/demo_e2e 与原版结果一致。

**任务 A02 — 对 v0.10 batch 行为做失效模式审查**
- 审查 scripts/batch_production.py 的 plan hash、schema、同步锁、partial step、异常处理、状态写入、源权限变更、路径 symlink、已有 Run 绑定、跨进程并发。
- 产物：failure modes 对照表及缺陷修复 PR；不改变旧 batch JSON 行为。
- 验收：故障注入测试证明任何不确定“完成但未落盘”的 Host action 不会被静默重跑。

**任务 A03 — 批次全链路持久化**
- 对失败阶段 write-ahead journal、atomic write/rename、output existence、临时目录残留、磁盘空间不足、进程 SIGTERM 做状态协调；原始事件和图片仍不可覆盖。
- 产物：可重复的 crash/recover 测试，附恢复或人工 reconcile 的确定性结果。
- 验收：不出现两个同 ID 通过或重复调用；在证据不完整时 BLOCKED。

**任务 A04 — 受控预算**
- 模型调用上限、批次最大任务数、单资产修复/重生成、终止条件、取消及状态查询；无隐形第三方模型后备。
- 验收：耗尽后没有新的模型调用；用户能通过 CLI 清楚看到 PAUSED/BLOCKED 和预算使用。

**任务 A05 — 权限和 provenance 负面案例**
- 非商用、未知 license、改名/挪动审查文件、CC-BY 署名缺失、人审缺失、SHA 篡改、model origin 伪造；且不得因单纯 license allowlist 自动声称法律合规。
- 验收：所有禁止的案例阻断；正常可商用记录能通过输入校验但仍等待实际审核。

**任务 A06 — 量测初始化**
- 把历史 LAMP/RADIO 真实记录只读导入 benchmark（2 个资产/3 次 image gen）并标识为 legacy evidence；人工确认对齐可比性。
- 验收：绝不把历史 synthetic tests、模拟 PNG 或 Unity capture 混入“新 v0.10 实际批量成功率”。

**任务 A07 — CI 与故障闭环**
- 原有 GitHub Actions workflow 加 regression 标签、只读 provenance schema 检验及失败原因摘要，不上传私人 PNG/私有 Build。
- 验收：旧 178 测试全部通过，新增测试全部通过，CI 成功，有可重现故障样本。

## 4. v0.11 — 智能美术规格与参考图系统（P0）

**任务 B01 — AssetSpec v2**：按 concept/reference、UI icon/sprite、background、texture-candidate、VFX sheet、Steam capsule 分类，新增模式/尺寸/alpha/颜色空间/用途/主视角/审核要求；保持旧 TOML 兼容；schema 与 migration tests。

**任务 B02 — Reference Authority 版本锁**：结构 Master、材质 Master、镜头 Master、Style Reference、局部目标图权威清晰且不能相互覆盖；角色冲突和不完整参考必须 BLOCK；提供 human-approved 标志与 SHA 的审计语义。

**任务 B03 — 设计提示词编译器升级**：从单次请求生成任务分解、正/负约束、分层 delta、材料和镜头协议；“修复”只修改失败区域，不无条件重新设计整体。

**任务 B04 — Style Kit**：多资产统一 palette、light rig、材质语汇、边缘、视觉密度、对比、UI 字体/间距（UI Harness 决定交互）、图集画幅；支持用户项目级版本冻结。

**任务 B05 — Category Templates**：道具概念/场景背景/UI icon/alpha Sprite/VFX Sheet/texture 候选/Steam key art 示例和一键创建；不提供伪造审核通过的演示版权声明。

**任务 B06 — KNIFE_001 权威对账**：把 v030E 和用户最新已确认设计引用明确记录，不把九张参考图/四幅 clay 视图推断为批准 Full Tang/PBR；需用户确定冲突后方可锁定 Master。

**任务 B07 — 数据协议 E2E**：旧路径 bootstrap/edit/repair、旧 v0.9 Host 流程、v0.10 batch 都走迁移/兼容测试；无授权变更不得清除旧状态。

**v0.11 退出条件**：六类任务规格能生成明确 Host packet；硬性冲突全部 fail closed；样本风格规范经实际图像检视；后端无新 API 依赖。

## 5. v0.12 — 精确编辑和 QA 引擎（最高美术质量优先级）

**任务 C01 — 实际图像 QA 基准库**：使用已授权且 SHA 锁定的多风格来源/目标/正确输出/典型失败标签，严格区分人工标注与机器推断。

**任务 C02 — Region Mask Contract**：支持严格保护区、可变区、柔性过渡区、mask 文件 SHA、坐标系和色彩空间；重采样/对齐失败不得出数字通过证明。

**任务 C03 — Pixel QA**：统计 protected mismatch pixels、changed fraction、ROI 边缘漏改、SSIM/色差（视工具和样本可用性）、边缘 halo，产出透明热图和数值报告；目标与现有 region_quality.py 共存而不是覆盖。

**任务 C04 — 可证明零误改区域**：对 strict protected mask，在经过坐标验证且实际可用的条件下以保留原像素合成输出；合成后重新做整图 seam/视觉检查，不能只因 ROI 外零差异就判美术正确。

**任务 C05 — 语义硬门禁**：产品结构、材质部位、相机方向、组件数量和原版标识逐项判断；无法确定则 NOT_VERIFIABLE；不允许视觉 critic 自己编造图片内容作为 PASS。

**任务 C06 — 独立视觉校准**：批量盲评机/人错误样本；对批次中可能漏检的瑕疵进行抽样质检并形成 confusion matrix；所有真正 release 资产需明确负责人的最终艺术 signoff。

**任务 C07 — 自动修复预算**：REPAIR_MINOR（局部）/REGENERATE_MAJOR（不批准结构前不得替换 Master）/BLOCKED；同一缺陷持续复现时自动停止，避免无限成本。

**任务 C08 — 技术 QA 和材质语义**：PNG/WebP 尺寸、alpha 光晕、颜色空间/数据贴图、平铺纹理、Sprite 帧分割、LOD/压缩适配；PBR 候选不可被自动当作物理验证合格。

**任务 C09 — 真实 A/B 质量对照**：与 v0.9 LAMP/RADIO 使用相同原始源和可比区域重新做真实生成评测；记录主观认可率、失败项及 ROI 漂移，未改善时禁止宣传性能提升。

**v0.12 退出条件**：机器报告绑定原始图片；严格保护区在可比且适用场景按 contract 为 0 误改；QA 假阳性有可测验证集；真实/模拟指标不混算。

## 6. v0.13 — 真实批量游戏素材生产（P0）

**任务 D01 — 多品类真实样本 Pilot**：至少 12 个经过权利核查的独立真实任务，覆盖至少四类游戏图片，收集实际 native generated_images、events、Receipt、QA、产出 hash、生成操作数。少于 12 个仅算 smoke。

**任务 D02 — 扩充至候选规模**：至少 30 个独立真实任务，场景涵盖 edit/first-master/纹理候选/界面图标/背景/商店候选；不能由 mock 替代。

**任务 D03 — 多种失败处理**：无 Codex 登录、503/容量不足、断网、CLI 意外退出、磁盘满、图像缺失、丢事件、宿主返回非法 JSON；都要可见错误码、停止且不隐式重复生成。

**任务 D04 — 完整良率统计**：记录 first-pass rate、final-pass rate、repair count、regenerate count、manual intervention rate、blocked breakdown、non-target drift、真实 Host actions；报告按类别拆分。

**任务 D05 — 稳定队列**：batch 顺序/可选有界并发；避免多队列共享一笔不可追踪的宿主任务；预算和任务公平调度，默认并发 1。

**任务 D06 — 产物审计重验**：任何 batch accepted 后对每一个 asset 做 production_audit；copy 和 hash 失败拒绝 Unity staging。

**任务 D07 — 局部人工批准插槽**：需要设计/权利/引用权威确认时停为 REVIEW_REQUIRED，不消费新的 imagegen 调用；批准后保留审批人和输入 SHA，再继续后续步骤。

**任务 D08 — 可读报告**：CLI/JSON/Markdown 三种输出，避免为了看状态强制部署 Web UI；可选择接入既有 AI 工作台 UI，但不作为生产的必要依赖。

**v0.13 退出条件**：达到配套 Acceptance 文档的真实批次量与良率要求、证据完整度、故障恢复与人工抽审要求；不得把 30 个全为同一风格的任务冒充跨风格验证。

## 7. v0.14 — Unity 实际资产交付（P0）

**任务 E01 — Release Manifest v2**：Image role、format、alpha、sRGB/linear、TextureImporter type、Sprite PPU、filter/wrap/mipmaps、compression target、rights lineage、审计绑定。
**任务 E02 — Import Adapter**：独立 Unity 版本兼容的 Editor 接口，读取白名单相对目录，校验 SHA，按模板应用 importer；记录 import success/failure；严格保护原有 GUID/.meta。
**任务 E03 — 隔离验证**：仅在干净 Unity worktree/副本或微型专用 Unity QA 工程内运行，不修改 Second Life Workshop 主线脏工作树。
**任务 E04 — 真实 Sprite/背景**：准备/加载 Sprite、背景和 UI 图标，确认 alpha、sRGB、边缘、Mip/压缩、小尺寸显示一致性。
**任务 E05 — 贴图和材质候选**：校验不同 channel 语义、Unity 贴图格式/纹理坐标，禁止物理错误的图直接应用到游戏中。
**任务 E06 — Player Capture 与 Diff**：Game Player 实际启动，记录 build commit、截图 SHA、分辨率、相机/场景、屏幕画面和材质显示差异。
**任务 E07 — 性能预算**：量测加载耗时、纹理内存、帧时间等相对既有基线的增量，预算由目标平台和实测确定；不得凭漂亮截图写 PASS。
**任务 E08 — 7 类独立测试联动**：调用 ai-3dgame-test-harness 的同 commit release 证据；至少涵盖 Editor/physics/Player visual/OS input/paper cut/performance/nondev build。
**任务 E09 — 已知游戏阻塞管理**：磨刀石选择 Player 失败、切纸/物理、HUD 等不属于图片生成模块，关联到游戏仓库任务；不能因此给 Image Harness 生成能力虚假 PASS，也不能跳过最终游戏发布阻塞。

**v0.14 退出条件**：至少三类真实 ImageGen 资产在 Unity 实机 Player 端可见并通过对应 QA；完整发布需所有适用七类独立测试成功。

## 8. v0.15 — 商业授权、Steam 美术包和权属审计（P0）

**任务 F01 — Source Lineage**：对每个输入/参考图/字体/模板/第三方模型/贴图/派生资产记录作者、来源 URL、证据文件、SPDX ID、许可证文本 SHA、署名、范围、负责审核人。
**任务 F02 — 法律红线**：拒绝非商用/未知/冲突条款；商用 license allowlist 只是预检，不等于司法判断；商标、人像、声誉风险需要人审。
**任务 F03 — 依赖 SBOM**：记录项目依赖许可证和其实际分发方式，禁止将第三方代码许可证等同素材版权许可；对新增开源工具单独做商用审查。
**任务 F04 — Steam 图像规格**：按发售当天官方模板检查 Capsule/Library/Icon 等尺寸、alpha/format、Logo/正文限制；错误立即 BLOCK。
**任务 F05 — 商店图和游戏截图分离**：生成艺术图只能用于允许的营销图类别；必须用真实 Unity Player 捕获 gameplay screenshots；不能 Blender/图生图冒充实机。
**任务 F06 — AI 声明资料**：从实际 shipped assets 生成 pre-generated AI 清单；若以后有运行时 AI，另存 guardrails/说明并人工复核；不自动提交表单。
**任务 F07 — 交付报告**：资产 Manifest、每项 QA、来源和人工审批、Unity same-commit proof、平台规格检查、遗留风险与签名摘要。
**任务 F08 — 禁止自动宣称批准**：最终机器状态只能 READY_FOR_STEAM_SUBMISSION_REVIEW；Steam/法务批准由外部实际证据完成。

**v0.15 退出条件**：任意缺权利、缺 Player 实测、缺商店内容审查均 fail closed；人类可阅读/复核全部来源证据。

## 9. v1.0 Release Candidate — 面向 Steam 的真实端到端验收

**任务 G01** 冻结对外协议：batch JSON、AssetSpec、master 审批、QA、Unity import manifest 版本与兼容行为。
**任务 G02** 至少 60 个真实且不同的有效生产任务、覆盖至少六类图像场景；先按该规模建立验证，再视错误分布扩大样本（不能把 60 个样本视为统计上绝对保证）。
**任务 G03** 真实生成全链路回归：reference -> prompt -> native image -> QA -> repair -> candidate -> approval -> unity stage -> import -> runtime proof。
**任务 G04** 同类资产风格一致性/游戏比例/KNIFE_001 严格身份质量单独验收；零 critical 漏检、所有发行素材人类终审。
**任务 G05** 批次断线/崩溃/并发/磁盘故障、不可重复扣费、不可伪造 receipt、伪造 Unity PASS 拒绝。
**任务 G06** 系统化 Unity Player 场景表现、压缩/Alpha/PBR 条件性测试和回归基线。
**任务 G07** 独立 ai-3dgame-test-harness 七类同提交 Release proof 通过，不能用 CI/mock 补齐缺失的真实 Player 证据。
**任务 G08** 完成实际素材授权、人类最后视觉批准、Steam 问卷资料和商店图准备；Valve 最终审核始终在外部。
**任务 G09** README/Runbook/故障恢复/操作视频或截图/CLI help/示例：一名使用者能从真实 brief 开始重复交付。
**任务 G10** 输出 Release Candidate 清单、已知不合格项与关闭条件；任何 P0/P1 阻塞存在时，版本停留 RC/BLOCKED，不强行发布 v1.0。

## 10. 跨项目依赖与责任

| 依赖 | 责任仓库 | 交付到本项目的证据 | 缺少时 |
|---|---|---|---|
| 3D 主模型和 GS 场景 | ai-3dgame-3D-harness | 批准模型/视角/材质来源 SHA、实际 Unity 渲染证据 | 3D 资产用途 BLOCKED，不阻断独立 2D 生成能力 |
| 高保真 UI 与交互 | ai-3dgame-ui-harness | 设计 Tokens、UI 布局和实际 UI 玩家截图 | UI 资产进入 Unity UI 需 REVIEW |
| Unity 游戏构建 | Second Life Workshop | game commit、build ID、真实截图、场景验证 | UNITY_VERIFIED 不可判通过 |
| 独立游戏 QA | ai-3dgame-test-harness | 七类 same-commit release manifest | STEAM_RELEASE_REVIEW_BLOCKED |
| 商用权利/Steam 审核 | 用户/原权利人/Valve | 授权来源证明、人工 signoff、适用内容申报、平台结果 | 未获审查，不能称可发售 |

不要将 image harness 的责任扩大成“修复所有 Unity 游戏 bug”，但需要将任何未通过的下游发布 gate 显示为依赖阻塞并可追溯。

## 11. 执行顺序及每个 Codex 工作单应包含的字段

每次只从最早的未通过 P0 开始；一项真实验证没通过不得把后续计划标记 DONE。任务单包含：
- task_id、issue_url、branch、base_sha、owner、priority、goal、scope、non_goals；
- exact files to inspect/modify、输入/输出 schema、向后兼容要求；
- deterministic tests、negative cases、真实模型/Unity 验证（如该项适用）、证据目录和最终 Gate；
- final git SHA、测试命令/退出码、原始指标、人类待审项、revert plan。
  
建议 Codex 每轮执行协议：
~~~text
Inspect existing state -> Recover task from this plan -> Reproduce deficiency
-> Smallest compatible change -> Unit/contract/negative tests -> Dry-run E2E
-> Real native ImageGen / Player test when required -> Evidence audit
-> Diff review -> Commit on feature branch -> CI -> Update acceptance/remaining blockers.
~~~

### 常规本机回归

~~~bash
cd /Users/qiguang/ai-3dgame-image-harness
python3 scripts/validate_project.py
python3 -m unittest discover -s tests -q
python3 scripts/demo_e2e.py
git diff --check
~~~

### v0.10 已有生产命令（真实执行会消费 ImageGen 能力）

~~~bash
./bin/ai-3dgame-image-harness batch validate --manifest <absolute-batch.json> --workspace-root <workspace>
./bin/ai-3dgame-image-harness batch run --manifest <absolute-batch.json> --workspace-root <workspace> --state <state.json> --max-jobs 2 --max-actions 8
./bin/ai-3dgame-image-harness batch run --manifest <absolute-batch.json> --workspace-root <workspace> --state <state.json> --resume
./bin/ai-3dgame-image-harness batch status --state <state.json>
./bin/ai-3dgame-image-harness batch unity-stage --manifest <absolute-batch.json> --workspace-root <workspace> --state <state.json> --output-dir <new-archive-dir>
~~~

严禁拿 example/demo rights 字段当真正授权；新模型和新宿主不可用时停机并报告，而不是擅自使用 API、跳过 QA 或生成占位文件。

## 12. 关键风险与处置

- **ROI 外变化**：v0.9 真实样本约 2.55%/15.95%；采用对齐+mask+原像素组合+接缝检查，按类重新量测。
- **模型 host 脆弱**：可能 503/CLI 格式变化或用量限制；契约适配层+幂等/无意外重试，模型不可用 BLOCKED。
- **错误视觉 QA**：独立的人审盲样、严重级别、错误样本持续扩充，不能只靠视觉模型自评。
- **假商用授权**：源码 SHA/审查人字段无法证明实际法律事实；人工审核原始来源，非商用不可通过。
- **图像假装 3D/PBR**：3D/GS 分工严格隔离，法线和 roughness 须条件性技术验证。
- **污染 Unity 工程**：仅在隔离 worktree/克隆上导入，回归通过后才由游戏项目独立合并。
- **发布平台规则变化**：不要长期依赖固化尺寸/AI 申报规则，发布前复核 Steamworks。
- **进度虚高**：分开报告“单测 PASS”“真实生成 PASS”“游戏实际 PASS”“Steam 审查”，禁止用总百分比掩盖最终阻塞。

## 13. 版本结果模板

每轮输出：
~~~text
Version / Branch / Base SHA / New commit SHA
Completed TASK IDs / Changed files / Existing functionality kept
Validator: PASS/FAIL + count
Unit tests: PASS/FAIL + count
E2E dry-run: PASS/FAIL
Real ImageGen: N calls / N accepted / failure categories / artifact SHA
Pixel & Visual QA: scoped metrics / human review evidence
Unity Editor/Player: build commit / screenshot SHA / 7-category status
License/Steam: reviewed/missing/blocked
BLOCKERS + concrete next task (first unpassed P0)
READY_FOR_STEAM_SUBMISSION_REVIEW: true only with all required evidence, otherwise false
~~~

详细的量化阈值和负面用例统一以 V1_ACCEPTANCE_AND_TEST_MATRIX.md 为准；本计划避免重复配置两份相互矛盾的数字。
