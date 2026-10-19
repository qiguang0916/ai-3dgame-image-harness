# ai-3dgame-image-harness v1.0 验收矩阵、生产基准与证据契约

> 状态：TEST_DESIGN_APPROVED_FOR_IMPLEMENTATION；并不表示当前 v0.10 已满足这些门槛。
> 基线：v0.10.0-dev / commit 7a7e35e；制定于 2026-10-19。
> 配套：V1_PRODUCT_AND_ARCHITECTURE.md、V1_DEVELOPMENT_ROADMAP.md。
> 最高原则：通过 deterministic unit/mock 不等于通过真实 ImageGen；保存 Unity 截图不等于游戏发布；哈希、用户自填审查字段不等于法律权利。

## 1. 严格区分的验收层级

| 层级 | 标识 | 证明内容 | 不能证明 |
|---|---|---|---|
| L0 | DESIGN_COMPLETE | spec/计划/验收标准自包含、可供实现 | 代码已完成 |
| L1 | CODE_VALIDATED | schema/unit/integration/mock/CI 正常 | 真实图像模型输出质量 |
| L2 | NATIVE_GENERATION_AUDITED | 真正 Host 执行，原生 PNG/事件/收据/输入绑定可回溯 | 美术质量、法律权利 |
| L3 | ART_QUALITY_ACCEPTED | 客观质量+独立视觉检查+必要设计人批准 | Unity 游戏中正确显示 |
| L4 | UNITY_VERIFIED | 隔离 Editor 导入/Player 实机画面与性能、对应 Game build 证据 | 全游戏七类 QA 都通过 |
| L5 | GAME_RELEASE_PROOF_PASS | 7 类完整且同一游戏提交、非开发构建证据来自独立 Test Harness | 法律权利和 Valve 审核 |
| L6 | READY_FOR_STEAM_SUBMISSION_REVIEW | 发行素材来源、人审、Steam 当前规则和问卷资料齐全 | Valve 最终审核、商业销量 |

任何指标或状态必须带 layer 字段；缺相应证据即 NOT_VERIFIABLE/BLOCKED，不能跨级自动升格。

## 2. 真实生产基准样本设计

### P0 Smoke（v0.13 前期）

- 最少 12 个 **独立真实** ImageGen 任务，覆盖至少 4 类图片，至少含局部编辑、从零生成、透明 Sprite、背景/材质候选。
- 每个必须保存前置 Rights record、Host packet、原始 native generated_images 源 PNG、事件记录、Receipt、最终 PNG、可复核 QA、失败原因和人审状态。
- 用来确认流程能工作和量化瓶颈；该阶段 **不依据成功数量认证 v1.0**。

### P1 Candidate（v0.13 退出门禁）

- 至少 30 个独立真实任务，覆盖至少 5 类素材；不得把同一个 Prompt 的 30 次重复当作五类任务。
- **观察到的**首次完整 QA 通过率目标 >=75%；最多 2 次有界修复/重生成后最终图像 QA 通过率 >=90%。样本不足、权限不完整或结果太相近，不能算通过。
- 100% 实际 Host 原生图像证据/输入 SHA/Receipt/critic 关联完整；任何漏检核心结构/License P0 风险不得出现未标识的“PASS”。
- 对每一个失败均应有原因码；没有完整原生 source 则视为 BLOCKED，不纳入成功分子。
- 对镜头和局部编辑类别单列 ROI 对齐/保护区误差，不将不可对齐图像删除后报告“0% 漂移”。

### P2 Release Candidate（v1.0 RC）

- 至少 60 个独立真实任务，覆盖至少 6 类实际游戏美术场景，包含 LAMP/RADIO 类型 delta、KNIFE_001 严格结构场景、UI 图标、背景、透明 Sprite、材质/商店候选；相同输入不能多次算独立样本。
- **样本观察值**首次完整 QA 通过率目标 >=80%；有界修复后最终完整图像 QA 通过率 >=95%；修复最多 2 轮/任务。报告必须同时提供每类分母与总体分母、95% 置信区间或适用的统计不确定性，不得将 60 个样本误写为总体质量保证。
- 实际上用于发售的所有资产（100%）有人工负责人的最终质量和权利审查；普通测试样本最少 20% 独立人工抽审，且必须包含每个素材类型的失败实例。
- 负面验证集中的 critical gate **0 个假 PASS**；发现任何 critical false accept 则必须阻断 RC、扩大测试并修复回归，不能仅依赖平均误检率。
- 每个实际发生的修复或重新生成有独立 Receipt、QA 和输入/输出 SHA，无覆盖旧产物和假执行事件。
- 无法实际完成上述规模验证时保持 RC 未通过，不能借模拟测试、计划文字或过往图像自动补数。

## 3. 量化 QA 验收矩阵

| ID | 检查项目 | 具体门槛 | 证据/失败处置 | 层级 |
|---|---|---|---|---|
| M01 | 来源和许可证 | 100% 来源拥有可审核条目；不确定/非商用/不兼容许可证 100% BLOCK | rights inventory + 审核文件 SHA + 人审；不能用 SPDX ID 代替合法性证明 | L1/L6 |
| M02 | Source Master | 必需参考图均为显式授权权威 SHA，无自作主张升级 | reference authority report；冲突 BLOCK | L1/L3 |
| M03 | Prompt/输入不变 | 0 次未记录 spec/input/Prompt 实质更改 | bound config/packet digest；SHA mismatch BLOCK | L1/L2 |
| M04 | 真实 ImageGen | 每次 production 生成必须有原生 PNG + 完成事件、Receipt，且匹配输出 SHA；0 个 fixture 冒充 | events.jsonl + native source SHA + production-audit；缺失 BLOCK | L2 |
| M05 | 基本图像 | 100% 实际可解码，匹配尺寸/格式/用途及 alpha 规范 | actual image decode + image metadata/technical report | L2/L3 |
| M06 | 严格保护区 | 图像坐标可比、保护区 mask 适用时最终锁定区域 0 像素误改；合成后边界须视觉 PASS | masked diff PNG/数值 + seam 视觉报告；不对齐 NOT_COMPARABLE | L3 |
| M07 | 柔性编辑区 | 非目标变化记录基准，设按类别适用阈值；任何异常扩散必须明确失败 | outside-ROI drift + heatmap + 人审签字 | L3 |
| M08 | 主体几何和身份 | 所有 required hard geometry/identity/topology gate 100% 真正证据通过 | 原图与真实输出对照、多视图；隐藏结构不可见则 NOT_VERIFIABLE | L3 |
| M09 | 风格一致性 | 实际独立审查中 >=90% 样本达 4/5 分或以上；所有发行素材需最终独立艺术审查 | style panel + 真实图集/小尺寸截图，不能只靠 CLIP 自评分 | L3 |
| M10 | UI 图标/精灵 | 指定目标尺寸实际辨认、Alpha 边缘/图集帧无实测严重瑕疵 | 小尺寸渲染、atlas 边界检查、UI Harness 审核 | L3/L4 |
| M11 | 材质贴图 | sRGB/linear、法线约定、通道用途和 Unity 导入配置全部符合 Contract | importer log + shader scene screenshot + 数据纹理检查 | L4 |
| M12 | Batch resume | 人为中断/并发/CLI 失败注入中 0 次证据不完整情况下重复 Host 生成；无静默覆盖 | 事件/Run ID/generation attempt 清单 | L1/L2 |
| M13 | Unity Editor | 所有待交付纹理可在隔离工程导入，目标 Prefab/Scene 正确引用，无 GUID 污染 | Editor Log + AssetDatabase import report + GUID diff | L4 |
| M14 | Unity Player | 真实 Player 中位置、尺寸、色彩、透明、视觉和材质通过审查；绑定实际构建提交 | Player source screenshots + build hash/commit + reviewer | L4 |
| M15 | 性能 | 与同场景基线相比新增纹理内存/载入/帧时不越过**事先按目标硬件写定**的预算 | Unity Profiler/Player logs；无预先 budget 不宣称 PASS | L4/L5 |
| M16 | 7 类游戏 QA | 每个适用类别同一实际 game commit 的独立真实证据 PASS | ai-3dgame-test-harness release manifest；缺一项 BLOCK | L5 |
| M17 | Steam 店铺图片 | 尺寸/内容/Logo 规则匹配发布当天 Steamworks，人工审查通过 | 当前官方 spec 版本 + 各原图 + 掩码/内容审核 | L6 |
| M18 | 游戏截图 | 真正 Unity gameplay；至少 5 张，>=1920x1080、16:9，非渲染概念图 | Player capture + SHA + build id，禁止 ImageGen 冒充 | L6 |
| M19 | AI Content Survey | 按实际上架内容整理所需 AI 申报及适用 guardrails，负责人复核 | 问卷记录及签字，不能由自动门禁声称已提交 | L6 |
| M20 | 最终提交准备 | 无 P0/P1 blocker；来源、质量、Unity、游戏和 Steam 审查完整 | release manifest + 所有 gate provenance；仅 READY_FOR_STEAM_SUBMISSION_REVIEW | L6 |

数值是拟定的工程目标门槛，不是现有实测成绩，也不是法律/Steam 官方强制的整体 AI 良率指标。观察到的数据应含样本大小、成功分母、置信区间及失败原因；若目标硬件或美术类别发生变化，先版本化更新 Contract，严禁测试之后为获得 PASS 反向调低阈值。

## 4. ROI 和历史基线比较规范

历史 v0.9：
- LAMP_001：outside-target changed fraction 约 2.54787%（历史 v0.5 约 2.26015%）。
- RADIO_001：outside-target changed fraction 约 15.95313%（历史 v0.5 约 13.94734%）。
- 这两个样本没有证明局部编辑精度改善。

新对照需满足：
1. 使用**同一原始批准 Master**，留存 SHA；各版本独立生成，不复用测试目标图。
2. 尺寸、颜色空间和对齐前提一致；仿射对齐参数显式记录，如结构/裁切变化不能合法对齐，报告 NOT_COMPARABLE。
3. 使用同一个由 reviewer 审定的 ROI/mask；严格保护区采用保留原图像素与 seam QA，柔性背景变化不强求 0。
4. 记录 (a) protected mismatches、(b) outside-ROI changed fraction、(c) changed area within target、(d) subjective target correctness、(e) source image visual integrity。分指标报告，不能选漂亮指标宣称全方位提升。
5. 至少同 LAMP/RADIO 各做多次真实验证，差异报告必须连同“未改善的样本”披露；同类比较应避免使用全局颜色/光照扰动引起的伪漂移与掩盖瑕疵。

## 5. 失效注入与负面测试（至少覆盖下述全部场景）

| ID | 故障 | 预期结果 |
|---|---|---|
| N01 | 未登录或 Codex 原生 image_gen 无法调用 | BLOCKED，无 API/local-model 后备 |
| N02 | provider 503/限流/执行超时 | 安全停止，保留尝试证据，不自动推断是否已消费 ImageGen |
| N03 | 原生 PNG 不存在、不是 PNG、SHA 不符 | 生产审计 BLOCKED，不能 staged |
| N04 | CLI JSONL 中 copy 命令失败/工具事件模糊 | provenance BLOCKED，绝不伪装模型身份认证 |
| N05 | 主机调用后进程终止但 state 未更新 | quarantine，先 reconcile，不自动重复调用 |
| N06 | 被改动的 asset/edit/rights 文件或 license 文本 | resume 拒绝，要求新批次或人工 reconcile |
| N07 | source rights 是 CC-BY-NC、未知/不兼容条款 | BLOCKED，不发出 model call |
| N08 | CC-BY-4.0 缺署名、缺 reviewer 或审查证明 SHA | BLOCKED |
| N09 | 伪造 QA gate PASS/重复通用 observation | QA 拒绝 |
| N10 | 局部 protected 区域被误改或图像失准 | FAIL/NOT_COMPARABLE，不能输出 0% 的虚假结论 |
| N11 | run-state 被另一批次复用/调换 | strict binding 失败，拒绝 staged |
| N12 | 已 ACCEPTED 的 Run 继续同批次 resume | 不触发任何新 image_gen |
| N13 | 并行任务写入同一路径/互相覆盖输出 | 锁/独占创建，冲突 ERROR/BLOCKED |
| N14 | 磁盘满、半写 manifest、JSON 只写一半 | atomic write 或隔离，正式发布 BLOCKED |
| N15 | synthetic stub Host result 假装正式来源 | production-audit 拒绝，不能 Unity staging |
| N16 | forged Unity Player screenshot / build hash 不匹配 | unity-proof / game test gate BLOCKED |
| N17 | Unity AssetImporter 颜色空间或 Normal 通道错误 | Editor/Player 验证失败 |
| N18 | 生成艺术图冒充真实 Steam 游戏截图 | commercial-gate BLOCKED |
| N19 | 包中缺 AI 使用披露、缺人审版权或素材无来源 | READY_FOR_STEAM_SUBMISSION_REVIEW 不得为真 |
| N20 | KNIFE_001 最新参考和已批准 v030E 相冲突 | REFERENCE_CONFLICT/BLOCKED，不能自动升权威 |

## 6. Unity 端的最低真实验证范围

在隔离 Unity worktree/QA 工程中，至少三类**经真实 ImageGen production-audit**的图像通过 Editor 导入和 Player 实测：
1. 小尺寸透明 UI icon / Sprite（Alpha 和缩放）；
2. 纹理/材质或木板背景（sRGB、mipmap、纹理密度）；
3. 工作台/刀具相关审定美术图片（要求准确主体轮廓、灯光/贴图在游戏视角一致）。
  
每个记录必须绑定：
- image production run ID / AssetSpec SHA / actual PNG SHA；
- source rights review 和 reviewer；
- Unity Project Git commit / build ID / Editor import log；
- scene/prefab + importer settings + Player screenshot SHA；
- QA verdict，视觉审查人、可重现实机命令；
- performance benchmark（基线与实际差异）。

历史 Second Life Workshop 0.2.0 的 Player 截图证明采集工具可运行，不等于本次新资产已导入，也不等于磨刀石选择故障已修复。若真实 game-test-harness 七类里有现存游戏玩法 bug，保持下游发布阻塞，交由游戏工程分支修复。

## 7. 商用许可与 Steam 规则测试边界

自动许可预检按输入、参考、模型权利/输出条件、字库、第三方脚本、衍生资产分别分类。当前 v0.10 代码中的 commercial allowlist、rights reviewer 文本和摘要只做**记录检查**；具体实际商用许可需验证原始授权来源和有无传播/署名/商标等附带条件。任何不确定项默认 BLOCKED。

截至 2026-10-19 核对 Steamworks 的主要官方约束（发布前复查）：
- 必备商店胶囊：Header 920x430，Small 462x174，Main 1232x706，Vertical 748x896；
- Library Capsule 600x900；Library Hero 3840x1240；Logo/其他槽位以当前官方模板另行校验；
- gameplay screenshots：真实游戏画面、至少五张，建议按官方指示 >=1920x1080 及 16:9；
- 基础 capsule 禁止无关广告、评论分数和促销文案；图片规范按图片槽位区别处理；
- Content Survey：需准确说明实际进入游戏的 pre-generated AI 内容；若游戏运行时用 AI 生成内容，另加 guardrails 说明要求。
  
来源：
- https://partner.steamgames.com/doc/store/assets
- https://partner.steamgames.com/doc/store/assets/standard
- https://partner.steamgames.com/doc/store/assets/rules
- https://partner.steamgames.com/doc/gettingstarted/contentsurvey

## 8. 推荐私有证据目录（不得公开上传用户资产）

~~~text
<workspace>/.ai-3dgame-image-harness/
  batches/<BATCH_ID>/
    immutable-plan.json
    batch-state.json
    jobs/<JOB_ID>.json
    jobs/<JOB_ID>.json.production/
      0000-imagegen_*/packet.json
      0000-imagegen_*/generated.png
      0000-imagegen_*/events.jsonl
      0000-imagegen_*/receipt.json
      0000-imagegen_*/attestation.json
      0001-visual_qa/qa.toml
      0001-visual_qa/events.jsonl
    quality/<JOB_ID>/
      technical-report.json
      region-diff.png
      roi-measurement.json
      visual-review.json
      audit.json
    rights/<JOB_ID>/
      source-rights-review.json
      source-license-evidence.txt
  unity-staging/<BATCH_ID>/
    unity-staging-manifest.json
    <JOB_ID>.png
  unity-proof/<GAME_COMMIT>/
    unity-editor-import-report.json
    unity-player-capture.json
    game-test-seven-category.json
  reports/<BATCH_ID>/
    production-benchmark.json
    human-review-summary.json
    release-readiness.json
~~~

目录为“目标形态”，不是声称脚本已经写出全部文件。现有 v0.10 使用 <state.json> 等路径实际形式保持兼容；额外目录以新增协议逐步演进。私有目录、旧真实来源图、截图和许可证原文始终由 Git ignore/访问控制保护。

## 9. 每版发版门禁

1. Code Gate：validator / unittest / demo_e2e / git diff --check / GitHub CI 全部通过（新增测试不得取代旧测试）。
2. Contract Gate：新增 Schema 有兼容测试和负面测试；无未经批准的 Masters 或源文件改写。
3. Native Gate：若该版涉及生成功能，应有新版本真实 ImageGen 结果、可验证事件原文/PNG/Receipt；仅 mock 版本不得宣称 L2。
4. Quality Gate：输出真实原图和 reviewer 的结构/局部/美术评价，实际样本 KPI 符合本矩阵。
5. Unity Gate：涉及导入则需要 Editor + Player 同一证据链，不能停在 PNG 暂存。
6. Release Gate：涉及游戏发布则需要独立游戏同提交七类证据、真实 rights review 和当前 Steam 政策检查。
7. 状态分类：COMPLETED_CODE / VERIFIED_NATIVE / VERIFIED_ART / VERIFIED_UNITY / RELEASE_REVIEW_READY / BLOCKED。只有满足对应层级才能写 DONE。

### v1.0 明确停止条件

任一条件触发即停留在未通过状态：关键来源许可未知；KNIFE_001 结构权威不一致；结构 hard gate 未验证；生产模型凭证缺失；RC 真样本规模或质量指标未达标；Unity 贴图导入、玩家画面、七类独立 QA 未通过；尚未完成 AI 披露、人审或其他适用平台限制。模型不可用也不允许自动购买/切换供应商。

## 10. Codex / 测试执行交接清单

- 阅读 docs/V1_PRODUCT_AND_ARCHITECTURE.md、docs/V1_DEVELOPMENT_ROADMAP.md、本矩阵与 AGENTS.md；
- 核对当前 HEAD、未提交状态、旧测试和所有已记录实际 blocking case；
- 找到最早未通过的任务 ID，先写可证明失败的测试，再改最小范围；
- 优先使用已有模块；新增依赖先核查商业许可、长期维护、实际工具必要性；
- 不合并私有参考图到公共 Git；真实 Host/Unity 实测在隔离路径完成；
- 每个提交附“执行命令、退出码、测试数量、真实样本分母、SHA、失败项目”；
- 缺完整证据不得称 Steam 商业 READY；下个任务取本计划中下一 P0。

### 现有回归命令

~~~bash
python3 scripts/validate_project.py
python3 -m unittest discover -s tests -q
python3 scripts/demo_e2e.py
git diff --check
~~~

最重要的原则：设计/测试目标现在可以完全定义，但 v1.0 的完成只能由未来实际生产证据、实际 Unity 游戏结果和必要人工/平台审查决定。
