# ai-3dgame-image-harness v1.0 总体产品与技术设计方案

> 文档状态：已完成设计、待分阶段实施（DESIGN_BASELINE，不代表功能完成）。
> 制定日期：2026-10-19（America/Los_Angeles）。
> 当前实现基线：v0.10.0-dev，分支 feat/v0.10-steam-commercial-production，提交 7a7e35e。
> 配套文档：V1_DEVELOPMENT_ROADMAP.md、V1_ACCEPTANCE_AND_TEST_MATRIX.md。
> 禁止将规划目标标记为已实现；任何新能力以源代码、真实运行记录和独立验收为准。

## 0. 决策与范围

项目定位：为“一人 + AI”Steam 商业游戏工作流提供可审计的游戏图像资产生产控制面。它不是新的图像基础模型，也不是通用 3D 几何生产器。沿用 Codex/ChatGPT 宿主内置 ImageGen 作为默认且唯一自动推理路径；不添加直接付费 OpenAI API、ComfyUI、CUDA、本地权重或第三方付费服务的静默后备；宿主不可用时 BLOCKED。

最终目标为：Asset Brief -> 来源及权利核查 -> 参考权威锁定 -> Prompt/Diff 编译 -> 原生 ImageGen -> 原始像素和主观视觉双重 QA -> 有界修复 -> 候选审查 -> Unity 导入与游戏实际验证 -> 商业交付审查。

“全自动”的工程含义：可自动编排可验证步骤，并对无法证明的环节失败关闭。素材权属、人像/商标、最终用户美术批准、Steam 申报及 Valve 审核必须保留可追溯的人类或外部审查，绝不伪造审批。

### 0.1 功能边界

| 资产类型 | Image Harness 所负责 | 明确不负责 |
|---|---|---|
| 2D 游戏道具概念、背景、图标、UI 装饰、贴花、VFX 精灵表 | 图像生成/编辑、版式/透明通道、质量与来源证据 | UI 整体交互行为与可用性验收（由 UI Harness 负责） |
| 图片驱动的游戏材质候选（Albedo/BaseColor、Mask 等） | 源图/贴图候选及语义和通道检查、导入验证 | 从图片假定生成真实 3D 几何、物理正确的 PBR 全套参数 |
| Steam 商店胶囊、库封面、Logo 候选 | 按当前 Steamworks 规范制作和校验尺寸及内容 | “生成图”等同实机截图；自动声明 Steam 审核通过 |
| 3D 模型配套参考图 / KNIFE_001 多视角辅助 | 不改变权威 Master 的辅助参考和材质风格审查 | 隐藏 Full Tang 几何推断、GS/mesh 生产；转交 3D Harness |
| Unity 纹理、Sprite、背景 | 标准化、只读暂存、受控导入和 Player 截图比对 | 全游戏交互/物理故障修复；由 Game/Test Harness 管辖 |

目标首要消费者：Second Life Workshop Unity 项目。先在隔离 Unity worktree/复制项目中验收；未经确认不覆盖用户正在开发的脏工作树、不修改历史 .blend/GLB Master。

## 1. 已验证基线（事实，不是规划）

- v0.9 已对 LAMP_001（1 次）和 RADIO_001（2 次、1 轮修复）执行原生 ImageGen/独立视觉 critic；这只验证小样本工作流。
- v0.9 有原生 source PNG、Codex 事件记录、Receipt SHA 关联，以及实际 Unity Player 三帧截图收集。
- v0.9 发现 LAMP/RADIO 非目标区域变更比例约 2.55%/15.95%，不能宣称精细编辑优于旧版本。
- v0.10 新增 scripts/batch_production.py、不可变批次配置/权利证据摘要、可恢复顺序任务、真实审计后 Unity 原样 PNG 暂存。
- v0.10 开发验证：178 个 Python 测试通过、示例验证通过、host protocol dry-run E2E 通过，GitHub Actions validate 成功；**没有 v0.10 多素材真实运行验收**。
- 真实游戏曾发生磨刀石选择验证失败（exit 1）；Unity 完整七大类同提交证据尚缺。其余参阅 docs/V09_COMMERCIAL_BLOCKERS.md、docs/V10_ACCEPTANCE.md。

## 2. 目标用户使用路径与生产模式

### 2.1 操作模式

- BOOTSTRAP_MASTER：无已批准 Master 时生成候选，不自动提升为权威。
- DELTA_EDIT：对已批准图像限定区域、组件和材质变更；保留不应改变的部分。
- STYLE_SERIES：在同一设计体系下生成成套图标、贴花、纹理候选或宣传图候选。
- TEXTURE_CANDIDATE：按用途输出 BaseColor/Mask 等候选；必须标识非物理认证的生成通道。
- UNITY_ASSET：生成和审计游戏用 2D/Sprite/Texture/Atlas 候选，独立 Unity 导入后方可升格游戏可用资产。
- STEAM_MARKETING：各商店图尺寸、Logo/文案合规检查、人工内容审查；实机截图只能来自 Unity Player。

### 2.2 典型任务的 Definition of Done

示例：KNIFE_001 刀面精细修改。必须绑定用户已批准的具体 Master 和当前 Unity 版本、保护轮廓/比例/刀尖/刀背/柄结构，指定修改区域与材质目标，执行真实编辑、SHA 绑定 QA、多视角对比与游戏实际观感验收。**不能默许将其他历史刀具或九张新参考图提升为新的几何权威**。

示例：游戏 UI 图标集。要求统一线宽、视觉密度、背板风格、留白和透明边缘；生成多个候选后经跨图集一致性与小尺寸实际可读性测试，交付 UI Harness 做交互实现。

示例：木质桌面背景。要求背景无工具和刀具、远景纹理密度合理、光照统一、Unity 近景实际显示无明显重复纹理，源图片和派生贴图独立留痕。

## 3. 分层技术架构（复用现有模块）

~~~text
User Brief / Approved Master / Game Art Rules / Reference SHA
                   |
    Asset Contract + Rights/License Preflight
                   |
  Prompt Control / Authority / Topology / Region Lock
                   |
   Immutable Batch Plan + Atomic State/Attempt Journal
                   |
    Native Codex Host (ImageGen, no API fallback)
                   |
   Source PNG + Host Events + Packet/Receipt/Hash
                   |
   Technical QA -> Pixel QA -> Independent Visual QA
                   |
       PASS       REPAIR       REGENERATE      BLOCK
         |            \             /             |
    Candidate        bounded changes              |
         |                  |                      |
    Human/Design Approval <-------------------- HOLD
         |
  Immutable Packaging + Content Addressed Evidence
         |
 Unity Stage -> Isolated Editor Import -> Actual Player
         |
  Independent Game Test Harness Seven Category Release
         |
 Rights + Store Policy + AI Disclosure -> Submission Review
~~~

现有可直接复用：scripts/compile_brief.py、prompt_control.py、next_action.py、execution_loop.py、native_codex_host.py、production_autopilot.py、batch_production.py、region_quality.py、asset_report.py、production_audit.py、commercial_art_gate.py、unity_release_bridge.py、master_lifecycle.py。新建代码只能填补明确缺口；不要重写原有状态机、另起图像模型或重建 Unity。

计划新增边界清楚的扩展：
1. asset_contract_v2：定义按资产类型的尺寸、颜色空间、权威参考、用途、硬门禁；
2. measurement_suite：保存真实输入/输出 ROI 掩码、对齐参数、漂移、透明边缘和类型化质量指标；
3. production_benchmark：多素材、多版本统计，报告成功率、修复次数、失败原因和人工误接受率；
4. asset_release_manifest：将源/变更/权利/QA/Unity 导入与实际 Player 证据联结；
5. Unity Import Adapter（独立项目、受控安装）：只消费审核通过的 manifest，保持 GUID/Importer 配置一致；
6. Steam Store Checklist：独立于游戏图片发布，并在发售前读取最新官方规范。

## 4. 数据模型与权威链

### 4.1 AssetSpec（规划 Schema v2；兼容旧 TOML）

必填：schema_version、asset_id、request_id、mode、asset_category、intended_use（reference / ingame / marketing）、size_contract、quality_tier、style_profile_id + sha256、approved_reference_ids、source_rights_ref、output_contract。

可选：region_contract（目标区域/受保护区域/容差）、style_family、camera_contract、required_components、palette_contract、texture_semantics、game_scene_target、batch_budget、prompt_intelligence。

兼容策略：既有 v0.6-v0.10 manifest 原字段语义不变；新字段先 opt-in，迁移器显式升级且保留旧文件和 SHA，不允许静默复写 Master 或历史 Run。

### 4.2 Evidence 与生命周期

- MASTER_APPROVED：用户明确批准且内容地址固定，只读。
- CANDIDATE：已生成且 QA 通过，但不等于批准 Master。
- QA_ACCEPTED：图像合同的必需硬门禁通过；仅是图像生产状态。
- UNITY_STAGED：原生 PNG 和生产审计通过；**不是 Unity 已成功导入**。
- UNITY_VERIFIED：隔离 Editor 导入、运行截图/性能和游戏用例对应证据通过。
- RELEASE_REVIEW_READY：Rights/Steam/所有要求的同提交游戏测试完成，可交由人和平台最终审核。
- BLOCKED/QUARANTINED：信息缺失、非商用权利、不可验证、损坏或状态不确定；严禁“补填 PASS”解除。

证据链：AssetSpec SHA -> 批次计划 SHA -> Host packet ID -> 输入参考 SHA -> 实际原生生成 PNG SHA + Codex events transcript SHA -> Receipt ID -> Pixel QA + 独立 Visual QA -> Approved candidate -> Unity Import Manifest SHA -> Game build commit + Player screenshots -> Release checklist。

SHA 证明字节关联，不证明原始作者、合法权益、模型真实身份或审美质量。Native Codex 已有的 generated_images 复制证据并非密码学模型身份签名；诚实保留此边界。

### 4.3 批次状态和恢复

批次 job 固定为 PENDING / PAUSED / ACCEPTED / BLOCKED / ERROR，沿用 scripts/batch_production.py。ImageGen 的一次调用是不可轻易重放的副作用：
- 重启前先检查已有 Run、分步骤目录、SHA、来源证据和 Receipt；
- 若 Host 调用完成但原始证据不完整，先 QUARANTINE/人工调查；不能自动再次生成；
- 所有新报告采用临时文件+fsync+原子 rename；最终生成物和审计记录不得覆盖；
- 预算按 batch、asset、repair、regeneration、host actions 分层设置；限额用尽停止；
- 时间戳、错误原因码、重试序号和运行指标必须能够复盘，但不得持久化密钥、隐私输入或错误栈里的敏感数据；
- 同一批次不能因为换了机器、cwd、参考图片内容或许可证文本而静默重绑定。

## 5. 设计约束与图像质量算法

### 5.1 通用硬门禁（失败立即 BLOCK 或走有界修复）

- 正确 PNG/WebP 格式、可解码、像素尺寸、alpha 用途、位深/色彩空间、大小约束；
- 输入来源和批准参考 SHA 一致，输出非空、非占位符、未复制旧结果冒充新图；
- 结构/组件数量/关键视角、刀具主角身份、保护区域、图像用途和参考优先级；
- 无法从单张图证明隐藏结构时必须 NOT_VERIFIABLE；不因 critic 文本写 PASS 就放行；
- 保证来源许可在当前用途下受理、署名和人工审查留痕；
- 对 Steam 实机截图，来源只能是真实 game Player（禁止 ImageGen/Blender 静帧代替）。

### 5.2 像素区域锁定

1. 将编辑对象固定到原图坐标系，保存归一化/像素坐标、掩码、羽化规则、保护区域和是否允许几何变化。
2. 有对齐失效/裁切变化时，ROI 漂移指标标记 NOT_COMPARABLE，不计算伪精度 PASS。
3. 对 strict protected mask 需要精确保护时，用原图层合成保留被保护像素，再专门检测接缝和光照违和；**只靠提示词无法保证逐像素不变**。
4. 对允许风格渐变的 soft region 使用通道像素差、结构相似度、边界误差等指标；阈值须按类型和真实 QA 基线校准，禁止一个阈值套所有素材。
5. 记录目标区域变化覆盖率、非目标区误改率、与历史版本的可比基准及人工审查结果。v0.9 的 2.55%/15.95% 是既有实验样本，不等于 v1.0 允许阈值。

### 5.3 游戏美术质量

- 结构：正交视图与 3D 主模仅比较可见轮廓；多张图须来源一致、不可隐式补全未知部分。
- 风格：材质、光线、色温、边缘处理、色板、透视和目标显示尺寸一致。
- UI：小尺寸（例如 24/32/64 px）清晰可辨、alpha 无白边、留白一致；交互可用性由 UI Harness 完成。
- 纹理：BaseColor sRGB；法线/roughness/metallic 等数据纹理使用 linear；法线约定、通道含义、Y 翻转、纹理拼缝、平铺率、mipmap 和压缩必须在 Unity Editor 实测。生成式图像不能无凭证宣称物理正确 PBR。
- VFX sprite：帧序、图集边界、透明通道、播放时序和循环连续性。
- 背景：统一光照、适度纹理、无无关道具，近景 Unity 屏幕占比和游戏主体层次通过验收。
- 商店图：构图/标题可读，图像内容规则以发售时官方 Steamworks 为准。

## 6. Unity 契约与跨 Harness 分工

Image Harness 只负责生成审计过的纹理/Sprite/Atlas 输出和导入建议：
- packaging 提供 asset_id、role、file SHA256、尺寸、色彩空间、alpha 模式、texture_type、sprite PPU、filter、wrap、mipmap、compression、build target、license lineage；
- Unity Adapter 必须先在隔离副本/工作树执行，校验所有输入 digest，按约定应用 TextureImporter，并产生独立 Editor 导入报告；
- 不得写入正在使用的游戏主工作树，不得覆盖已有 GUID 的 .meta，发现冲突中止；
- Unity Player 应从实际构建获取 screenshot、Scene/Prefab 路径、Game build SHA/commit、分辨率、纹理采样问题、帧时间与内存峰值；
- 对接 ai-3dgame-test-harness 的七类同提交 release proof：unity-editor / game-physics / player-visual / os-input / paper-cut / performance / nondev-build。
  
边界：
- ai-3dgame-ui-harness：UI/UX 结构、动态交互与可操作原型；
- ai-3dgame-3D-harness / WorldForge GS：3D/GS 几何、Unity 3D 渲染路径，不能由 Image Harness 生成参考图片冒充模型；
- Image Harness：上游图像素材、图像证据、素材格式与受控导入；
- Test Harness：独立测试和不可伪造的游戏交付证据；
- 主游戏仓库：游戏逻辑、物理、磨刀石选择和切纸交互的修复。

## 7. Steam 交付设计

商店图片与游戏截图严格分类。根据 2026-10-19 查询的 Steamworks 资料，目前常见商店胶囊尺寸：Header 920x430、Small 462x174、Main 1232x706、Vertical 748x896；Library Capsule 600x900、Hero 3840x1240。截图应是真实游戏操作，至少 1920x1080、16:9；Steam 官方文档要求商店至少五张截图。当前设计必须在打包当天重新核对最新模板，不能把尺寸常量视为永不过时。

基本商店 capsule 文字限定游戏名称、官方副标题和允许的艺术元素；库 Hero 等有独立文案限制。AI 预生成并实际随游戏交付的内容，需要按 Steam 内容问卷的具体要求准确申报；若以后改为运行时生成，需增加对应守护措施和申报。合规门禁的机器 PASS 表示“交由人类进行 Steam 提交审查”，绝非 Valve 已接受或法务认证。

参考官方链接：
- https://partner.steamgames.com/doc/store/assets
- https://partner.steamgames.com/doc/store/assets/standard
- https://partner.steamgames.com/doc/store/assets/rules
- https://partner.steamgames.com/doc/gettingstarted/contentsurvey

## 8. 非功能与安全需求

- 运行可追溯：每一批准、失败、修复与导出都有 SHA 和事件关联；生成结果不可被 CI fixture 冒充。
- 幂等：已接受步骤不重跑；partial result 不自动重付/重生成；单一任务锁 + 批次锁；atomic journal。
- 安全：只读基线、workspace path traversal / symlink 防护、最大文件和 JSON 大小、敏感信息不出日志、不把私有参考图推到 GitHub。
- 资源：限制批次并发和 Host 调用预算；最小投入优先，任何新后端/托管服务必须获得明确成本同意。
- 工程：Python 3.11+ 兼容；现有 unit/mock 合约测试继续通过；真实 ImageGen、Unity Player 和平台审核必须独立验证。
- 可观察性：按批次输出生产良率、修复次数、平均 Host actions、资源耗用、手工复核比例、漂移与假阳性；绝不把模拟推理数据汇入真实生产 KPI。
- 发布：所有 release 工件打包只读清单和适用授权记录；缺少人审、游戏内验证或合法来源则无法进入 READY_FOR_STEAM_SUBMISSION_REVIEW。

## 9. 版本交付条款

版本职责、PR 的明确任务和通过门槛见 V1_DEVELOPMENT_ROADMAP.md；验证矩阵、负面用例、真实生产最小样本和证据目录见 V1_ACCEPTANCE_AND_TEST_MATRIX.md。三个文档作为一套“spec -> plan -> QA/tasks”交接材料，可由 Codex 逐版本实施，每次只执行下一未通过的任务。任何真实质量、法规、成本事实变化必须通过新 PR 更新方案并记录依据。
