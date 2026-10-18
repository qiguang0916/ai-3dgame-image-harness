# Host Failure Protocol

Host/backend failures are persistent run events. Do not hand-edit run JSON.

## Command

~~~bash
python3 scripts/execution_loop.py mark-blocked \
  --run <run.json> \
  --reason-code host_native_imagegen_failed \
  --action imagegen_edit \
  --message "Built-in image edit failed."
~~~

Add `--retryable` only when a retry is genuinely allowed.

## Supported reason codes

- `host_native_imagegen_unavailable`
- `host_native_imagegen_failed`
- `host_native_imagegen_moderation_blocked`
- `generated_result_missing`
- `generated_result_unreadable`
- `visual_inspection_unavailable`
- `required_reference_missing`
- `edit_target_missing`
- `reference_unreadable`
- `reference_image_invalid`
- `reference_sufficiency_failed`

The blocker records:

- reason code;
- action;
- short non-sensitive message;
- retryable flag;
- UTC timestamp;
- repair/regeneration budget snapshot;
- history event.

Never store credentials, cookies, private request payloads, or secrets.

After `BLOCKED`, `next_action.py` must return `report_blocked`. No image generation may continue and API/CLI fallback remains disabled.
