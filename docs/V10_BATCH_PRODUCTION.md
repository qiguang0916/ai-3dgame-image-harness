# v0.10 — Steam 商用游戏图像：批量生产与证据控制

**当前状态：开发版。ImageGen v0.9 已有真实 LAMP/RADIO 生成和修复记录；v0.10 批量生产尚未完成新的真实多资产生产验收。不得宣称 Steam 商业交付已通过。**

目标是沿用现有的 Codex ChatGPT 登录与原生 ImageGen，不安装本地模型，不额外调用付费 API，不使用未经确认可商用的第三方资产。v0.10 在原有 v0.9 production_autopilot、Receipt、QA 和 Audit 上方增加逐项来源门禁、序列化任务队列、断点续跑与只读 Unity 导入暂存。

## 任务清单

批次 JSON 必须位于 workspace_root 中，最多 128 项；每项使用唯一安全 ID、workspace 内的 asset/edit TOML 和 SHA 绑定的授权审查证据。例子（以下并非真实许可声明，需替换为你实际审查过的资料和 SHA）：

~~~json
{
  "schema_version": 1,
  "batch_id": "GAME_ART_BATCH_001",
  "jobs": [
    {
      "id": "PROP_001",
      "asset": "art/PROP_001/asset.toml",
      "edit": "art/PROP_001/edit.toml",
      "rights": {
        "basis": "user_owned",
        "license_id": "USER_OWNED",
        "review_status": "REVIEWED_FOR_COMMERCIAL_USE",
        "commercial_use_reviewed": true,
        "reviewer": "Responsible human reviewer",
        "evidence": {
          "path": "rights/PROP_001.txt",
          "sha256": "REPLACE_WITH_REAL_64_CHARACTER_SHA256"
        }
      }
    }
  ]
}
~~~

basis 支持 user_owned、openai_generated_reference（须指定 OPENAI_OUTPUT_TERMS_REVIEWED）或 commercial_licensed。后者只接受 CC0-1.0、CC-BY-4.0、MIT、Apache-2.0、BSD-2-Clause、BSD-3-Clause、ISC、0BSD。**非商用授权（如 CC-BY-NC-4.0）直接阻断**。白名单只针对输入素材来源，不能替代模型权重、工具依赖或最终作品的独立许可评审。CC-BY-4.0 另强制记录 attribution 署名文本；本检查并不证明署名内容真实。人类审核声明及其文件哈希不能独立证明权属、许可真实性或正确署名。

## 使用方法

~~~bash
ROOT=/absolute/workspace
BATCH="$ROOT/batch.json"
STATE="$ROOT/.ai-3dgame-image-harness/batches/GAME_ART_BATCH_001/batch-state.json"

./bin/ai-3dgame-image-harness batch validate --manifest "$BATCH" --workspace-root "$ROOT"
./bin/ai-3dgame-image-harness batch run --manifest "$BATCH" --workspace-root "$ROOT" --state "$STATE" --max-jobs 2 --max-actions 8
./bin/ai-3dgame-image-harness batch run --manifest "$BATCH" --workspace-root "$ROOT" --state "$STATE" --resume
./bin/ai-3dgame-image-harness batch status --state "$STATE"
./bin/ai-3dgame-image-harness batch unity-stage --manifest "$BATCH" --workspace-root "$ROOT" --state "$STATE" --output-dir "$ROOT/UnityArtStaging_001"
~~~

validate 是不调用模型的真实引用充分性与来源审查预检。run 只调用已存在的 Codex 原生 ImageGen/独立 QA 路径；每次尝试最多 max-jobs 个任务，每项最多 max-actions 个原状态机动作。中途退出可 --resume，已 ACCEPTED 的 Run 不会二次生成。发现残缺执行步骤、已 BLOCKED/ERROR 任务、输入资产、授权证据、TOML 或计划哈希变化时，**不自动二次支付或生成**；必须人工调查和新建批次。

返回码：0 仅表示所有单项生产 Run ACCEPTED（**不是 Steam 商用认证**）；2 表示阻断；3 表示暂停或仍有待处理项。

unity-stage 只允许所有 Run ACCEPTED、原生 Codex source PNG + 事件记录 + SHA-256 经过 production-audit 的结果；按原始字节复制 PNG，产出 unity-staging-manifest.json。不修改现有 Unity 工程，不进行 Master 自动提升，也**不代表已通过 Unity Editor/Player 游戏内验收**。

## 验收边界

- v0.9 基线：168/168 单元测试，Validator 与 Host 协议 dry-run E2E 均 PASS（2026-10-18）。
- v0.10：新增批次许可/状态/恢复/暂存阻断测试；本轮重新运行完整测试并记录实际结果。
- 真实 v0.10 多任务 Codex ImageGen、不同品类视觉质量、误接受率和参考区域漂移指标：**尚未通过独立生产验收**。
- KNIFE_001 真实游戏美术质量、PBR/Unity 7 大类同提交构建验证、人类版权授权审查、适用的 Steam AI 内容申报及 Valve 最终审核：**继续 BLOCKED**。

这是一套可审计控制与产线代码，不是一个新图像模型，也不应以模拟测试替代真正的 Steam 发售质量。
