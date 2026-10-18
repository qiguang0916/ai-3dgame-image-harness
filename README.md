# AI 3D Game Image Harness

**Current development branch: v0.6 — Professional Game Asset Production.**

This is a Codex/OpenAI **game image production Skill and auditable QA harness**, **not** an image generation model. The official built-in OpenAI `$imagegen` is the sole default image generation/editing backend. No API key, paid fallback, local diffusion model, or GPU inference runtime is introduced by this project.

Repository: https://github.com/qiguang0916/ai-3dgame-image-harness

## 能解决什么

- **从零生成首张 Master**：`bootstrap → imagegen_generate → Receipt → Visual QA → Candidate → Approved First Master → Active Manifest`。
- **已有素材精细修改**：选择当前批准参考图，按 Delta Brief 修改局部，保护指定区域。
- **游戏美术规范**：按视觉风格、材质、配色、光照、相机和游戏实际展示尺寸构造专业提示词；借鉴 Apache-2.0 的 Create Game Assets 方法，不强制安装第三方 Skill。
- **证据驱动 QA**：图像实际像素变化、组件/拓扑视觉检查、PNG 大小/透明通道、Master/Receipt SHA-256 绑定。
- **修复与重大重生成**：局部缺陷走 REPAIR_MINOR；结构问题走 REGENERATE_MAJOR；不可验证的情况 BLOCKED，预算有限制。

## 一条命令入口

在本仓库下：

```bash
./bin/ai-3dgame-image-harness doctor
./bin/ai-3dgame-image-harness version
./bin/ai-3dgame-image-harness validate
./bin/ai-3dgame-image-harness master --help
./bin/ai-3dgame-image-harness region-qa --help
```

`doctor` 的 `ready` 仅代表确定性 QA 依赖齐备；**不能证明当前 Codex Host 有 ImageGen**。

### 从零创建第一个 Master

从 `examples/BOOTSTRAP_PROP_001/asset-bootstrap.toml` 和 `create.toml` 开始：

```bash
./bin/ai-3dgame-image-harness init \
  --asset <bootstrap-asset.toml> --edit <create.toml> \
  --output <runs/create.json> --workspace-root <workspace>
./bin/ai-3dgame-image-harness next \
  --asset <bootstrap-asset.toml> --edit <create.toml> --run <runs/create.json> \
  > <packets/01.json>
```

由 **Codex 宿主内置 `$imagegen`** 执行 Packet 的 `imagegen_generate`，保存真实 PNG。再按 `references/execution-receipt.md` 记录并实际检查像素，写完整 QA，经 `qa` 转为 ACCEPTED，创建 Candidate：

```bash
./bin/ai-3dgame-image-harness master candidate \
  --image <outputs/master-draft.png> --source-run <runs/create.json> \
  --reference-id MASTER_R1 --revision 1 --out <candidate.json>
./bin/ai-3dgame-image-harness master finalize \
  --candidate <candidate.json> --qa <qa/master-qa.toml> \
  --approved-image <references/master-r1.png> --out <approved.json>
./bin/ai-3dgame-image-harness master register-first \
  --bootstrap-asset <bootstrap-asset.toml> --decision <approved.json> \
  --roles identity geometry material camera style \
  --out <asset-active.toml>
```

**严禁跳过真实生成、Host 视觉审核和批准，不能把 Candidate 当成 Approved Reference。** 完整说明：`references/first-master.md`。

### 精确局部编辑

在 `edit.toml` 内增加可选 `[region_contract]` 与 `[[region_contract.targets]]` / `[[region_contract.protected]]`，使用 0..1 坐标描述允许修改和受保护区域。此协议 **不声称宿主支持原生 Mask 编辑**，其主要价值是生成前的空间约束和生成后的客观检测。

```bash
./bin/ai-3dgame-image-harness region-qa \
  --edit <edit.toml> --reference <approved-master.png> \
  --result <edited.png> --output <region-report.json> \
  --diff-image <diff-heatmap.png>
```

`enforce` 模式下，`apply-qa` 会**重新读取、计算像素**，核验 `visual.region_preservation`，而不是相信手写的 PASS。参见 `references/region-quality.md`。

### 技术导出标准

可在 `[output]` 设置可选 `expected_size = "1536x1024"`、`require_transparency = true/false`；`image.technical_output` 成为必需 Hard Gate：

```bash
./bin/ai-3dgame-image-harness asset-report \
  --edit <edit.toml> --image <edited.png> --out <technical-report.json>
```

详情：`references/technical-output.md`。

## 开发验证

```bash
python3 -m pip install -r requirements-quality.txt  # macOS 已安装时无需重复执行
python3 scripts/validate_project.py
python3 -m unittest discover -s tests -v
python3 scripts/demo_e2e.py
```

真实 OpenAI ImageGen 只能由具备该能力的宿主执行。单元测试、模拟图片、Host attestation、静态校验都**不能单独证明真实模型输出质量**。

## 向后兼容与目录

- v0.5 manifests 不含新字段时，保留原有 Master/Receipt/Packet/QA 行为；
- 旧运行目录 `.game-image/` 继续忽略，原有 E2E 证据不移动或删除；
- 新本地运行结果建议使用 `.ai-3dgame-image-harness/`；
- `$HOME/game-image` 可以作为旧版只读基线，当前项目在 `$HOME/ai-3dgame-image-harness`。

## 真实验证边界

离线 v0.6 回归可以验证全流程代码和区域 QA。新的真实 Host `$imagegen` E2E、重大结构再生成与复杂 `KNIFE_001` 参考资产仍须由当前 Mac Codex Host 分别执行；没有证据时不得宣称质量提升或 v1.0 READY。进度详情见 `docs/V06_ACCEPTANCE.md`。

## v0.7 — Intelligent Prompt & Reference Control (opt-in)

The v0.7 extension enriches pre-ImageGen prompts without introducing a second
model, local GPU, API key or paid CLI. Existing v0.6 requests behave the same
unless `[prompt_intelligence]` is explicitly enabled.

```bash
./bin/ai-3dgame-image-harness styles
./bin/ai-3dgame-image-harness reference-review --asset <asset.toml> --edit <edit.toml> --workspace-root <workspace>
./bin/ai-3dgame-image-harness prompt-check --asset <asset.toml> --edit <edit.toml> --workspace-root <workspace>
```

The Host must actually inspect reference pixels before filling in visual facts.
New features include role-authority disambiguation, structured topology/camera
conflict checks, verified source SHA-256, concise game-art presets and mid-run
spec immutability. A source digest proves bytes, not the visual truth of a note.

See [v0.7 contract](references/v07-prompt-intelligence.md),
[v0.7 plan](docs/V07_PLAN.md),
and [quality-validation limits](docs/V07_ACCEPTANCE.md). Real ImageGen A/B
is not yet verified; added prompt text does not automatically improve quality.

## v0.8 — Steam Commercial Art Evidence Gates

Target: fully automated, stable game art production **with fail-closed quality
and rights controls**. Current v0.8 verifies GLB source-bound geometry views,
named components, proof-linked Unity Player integration and Steam store
asset dimensions; it **does not assert Steam approval or full automation**.

```bash
./bin/ai-3dgame-image-harness render-views --source <model.glb> --output-dir <new-folder>
./bin/ai-3dgame-image-harness canonical-qa --manifest <new-folder>/manifest.json
./bin/ai-3dgame-image-harness commercial-gate --manifest <package.json> --output <report.json>
```

A missing rights review, real visual inspection or Unity Player capture
blocks in-game release. A concept render cannot be used as a real Steam
gameplay screenshot. See [commercial spec](docs/V08_COMMERCIAL_TARGET.md)
and [KNIFE_001 evidence](docs/V08_ACCEPTANCE.md).

## Native Codex production autopilot (v0.9)

```bash
python3 scripts/cli.py autopilot run --asset path/asset.toml --edit path/edit.toml --workspace-root /absolute/workspace --run /absolute/workspace/run.json
python3 scripts/cli.py autopilot run --asset path/asset.toml --edit path/edit.toml --workspace-root /absolute/workspace --run /absolute/workspace/run.json --resume
python3 scripts/cli.py autopilot status --run /absolute/workspace/run.json
```

Requires authenticated ChatGPT Codex and built-in native imagegen. No API key,
fallback provider or local model. Optional `--codex /absolute/codex` selects the
executable; `--max-actions 8` bounds work per invocation. Existing state-machine
budgets still bound repairs and regeneration. Partial evidence blocks rather
than overwriting output or automatically repeating a host action. ACCEPTED emits
a non-commercial deliverable report, without Master promotion or Steam approval.
The new runner's live E2E is pending; see [v0.9 acceptance](docs/V09_ACCEPTANCE.md)
for the separate prior LAMP result and provenance/critic limitations.

## v0.9 — Unity release evidence bridge

Commercial in-game deliverables must pass the independent `ai-3dgame-test-harness`
seven-category same-commit release proof, not a self-declared Unity PASS.
This bridge never changes the user's Unity project:

```bash
./bin/ai-3dgame-image-harness unity-proof \
  --manifest /path/real-game-release-evidence.json \
  --commit <40-character-game-commit> \
  --output /path/immutable-unity-proof.json
```

The `commercial-gate` now also checks a bound `unity_integration.test_harness_release`
source file, the real Unity Player capture and matching build ID.
See [v0.9 Unity bridge](docs/V09_UNITY_RELEASE_BRIDGE.md).
Historical game QA bugs and missing rights evidence remain release blockers.

## v0.9 actual ImageGen + Unity Player delivery audit

```bash
# Native Codex subscription-only production with signed receipt, visual critic
# and bounded repair; no OPENAI_API_KEY or local image model.
./bin/ai-3dgame-image-harness autopilot run \
  --asset <asset.toml> --edit <edit.toml> \
  --workspace-root <workspace> --run <new-run.json> --max-actions 8

# Continue a persisted, auditable run without overwriting historical attempts.
./bin/ai-3dgame-image-harness autopilot run \
  --asset <asset.toml> --edit <edit.toml> \
  --workspace-root <workspace> --run <run.json> --resume

# Independently rehash the actual native source, all receipts, visual QA
# records, exact input/output PNGs and raw event transcripts.
./bin/ai-3dgame-image-harness production-audit \
  --run <real-run.json> --output <new-audit.json>

# Capture actual Unity Player HUD/knife A+B using engine screenshot API.
./bin/ai-3dgame-image-harness player-capture \
  --app <SecondLifeWorkshop-0.2.0.app> --output-dir <new-private-dir>
./bin/ai-3dgame-image-harness player-capture \
  --app <SecondLifeWorkshop-0.2.0.app> --output-dir <private-dir> --verify-existing
```

Real LAMP and RADIO native generation/repair were accepted; the real RADIO
production integrity audit and three real Unity Player screenshots passed.
**No Steam commercial release is certified**: independent full game QA,
complex KNIFE_001 visual approval, rights/provenance and relevant Steam
review/disclosure still require evidence. See `docs/V09_ACCEPTANCE.md`.
