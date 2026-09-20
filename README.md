# game-image

Game Image 是面向 ChatGPT / Codex 的游戏图片生产控制层。它不在本地跑图片模型；它负责把图片任务变成可验证的 reference、topology、QA 和状态机契约。

## v0.5

v0.5 在 v0.4 状态机基础上增加可审计执行：

- real runtime reference preflight；
- explicit edit target；
- reference sufficiency / provisional facts / prohibited assumptions；
- generic component topology contract；
- required hard-gate completeness；
- `NOT_VERIFIABLE`；
- host/backend blocker persistence；
- Host Action Packet v3 for auditable real runs (legacy dry-run packets remain v2)；
- bounded repair/regeneration；
- no automatic API/CLI fallback；
- Packet/input/result SHA-256 execution receipt；
- workspace-bound portable/resolved paths；
- QA/receipt/result digest binding；
- explicit topology count semantics；
- candidate → Master QA → immutable approved revision。

## 三种验证层级

**Static**

~~~bash
python3 scripts/validate_project.py
~~~

只验证 Schema 和跨文档关系，不要求二进制图片。

**Dry-run**

~~~bash
python3 scripts/demo_e2e.py
~~~

验证状态机/Packet 路由，不证明真实图片 Host E2E。

**Real runtime**

~~~bash
python3 scripts/execution_loop.py init \
  --asset <asset.toml> \
  --edit <edit.toml> \
  --output <run.json>
~~~

真实 run 默认检查 edit target 和 required references 是否存在、可读、可解码。只有测试 fixture 才显式使用 `--dry-run`。

## Host loop

~~~bash
python3 scripts/next_action.py --asset <asset.toml> --edit <edit.toml> --run <run.json>
~~~

Packet action 只会是：

- `imagegen_generate`
- `imagegen_edit`
- `visual_qa`
- `deliver`
- `report_blocked`

Host 必须服从 Packet 中的 edit target、references、requested delta、topology、reference sufficiency、required hard gates 和预算。

图片成功持久化后：

~~~bash
python3 scripts/execution_loop.py mark-generated \
  --run <run.json> --packet <packet.json> --result <image.png> \
  --receipt <receipt.json> \
  --host-attestation "Built-in imagegen executed this packet without fallback."
~~~

QA 后：

~~~bash
python3 scripts/execution_loop.py apply-qa --run <run.json> --qa <qa.toml>
~~~

Host/backend 失败：

~~~bash
python3 scripts/execution_loop.py mark-blocked \
  --run <run.json> \
  --reason-code host_native_imagegen_failed \
  --action imagegen_edit \
  --message "Built-in image edit failed."
~~~

## Contracts

- `references/runtime-preflight.md`
- `references/topology-contract.md`
- `references/reference-sufficiency.md`
- `references/visual-qa-contract.md`
- `references/host-failure-protocol.md`
- `references/host-action-protocol.md`
- `references/openai-imagegen-delegation.md`
- `references/execution-receipt.md`
- `references/master-lifecycle.md`

## Verification

~~~bash
python3 scripts/validate_project.py
python3 -m unittest discover -s tests -v
python3 scripts/demo_e2e.py
~~~

GitHub Actions runs the same repository checks.

## Remaining external verification

A green dry-run does not equal a real Host Image E2E. Before v1.0, run a neutral asset such as `LAMP_001` in a Codex host with built-in imagegen, persist the real run/packet/QA/output, and reach `ACCEPTED` or a formal `BLOCKED`.
