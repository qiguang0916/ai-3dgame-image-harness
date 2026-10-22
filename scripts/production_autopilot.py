"""Bounded, resumable native-host driver of the existing execution state machine."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import execution_loop as loop
from artifact_integrity import (canonical_json_bytes, resolve_in_workspace, receipt_digest,
                                sha256_bytes, workspace_relative)
from native_codex_host import NativeCodexHost, validate_critic
from native_strict_provenance import (
    compose_native_generation, is_strict_native_run, preflight_native_strict,
)
from next_action import build_from_paths
from validate_project import ValidationError, load_document


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(data)


def json_new(path, value):
    write_new(path, (json.dumps(value, indent=2) + '\n').encode())


def qa_toml(qa):
    lines = []
    for key, value in qa.items():
        if key != 'gates':
            lines.append(f'{key} = {json.dumps(value, ensure_ascii=False)}')
    for gate in qa['gates']:
        lines.append('\n[[gates]]')
        for key, value in gate.items():
            lines.append(f'{key} = {json.dumps(value, ensure_ascii=False)}')
    return ('\n'.join(lines) + '\n').encode()


def drive(asset, edit, workspace_root, run_path, *, resume=False, max_actions=8, host=None):
    root = Path(workspace_root).resolve()
    run_path = resolve_in_workspace(root, run_path)
    if not 1 <= max_actions <= 100:
        raise ValidationError('max-actions must be 1..100')
    # Separate orchestration lock spans subprocesses; state-machine locks stay short.
    with loop._exclusive_run_lock(run_path.with_name(run_path.name + '.autopilot')):
        evidence_dir = resolve_in_workspace(root, run_path.with_name(run_path.name + '.production'))
        if run_path.is_symlink():
            raise ValidationError('run state symlink requires manual reconciliation')
        if run_path.exists():
            if not resume:
                raise ValidationError('existing run requires --resume')
            run = loop.load_run(run_path)
            if Path(run['workspace_root']).resolve() != root or not run.get('auditable'):
                raise ValidationError('resume requires same auditable workspace')
            # Validate the *current invocation* even when already ACCEPTED;
            # otherwise a different asset/edit pair could inherit a green run.
            if (run.get('asset_document_path') != workspace_relative(root, asset)
                    or run.get('edit_document_path') != workspace_relative(root, edit)):
                raise ValidationError('resume asset/edit path differs from original Run')
            spec_sha = {
                'asset': sha256_bytes(canonical_json_bytes(load_document(Path(asset)).data)),
                'edit': sha256_bytes(canonical_json_bytes(load_document(Path(edit)).data)),
            }
            if run.get('input_spec_sha256') != spec_sha:
                raise ValidationError('resume asset/edit specification changed')
        else:
            if resume:
                raise ValidationError('cannot resume missing run')
            if evidence_dir.exists() or evidence_dir.is_symlink():
                raise ValidationError('orphan native Host evidence requires manual reconciliation')
            run = loop.init_from_paths(asset, edit, workspace_root=root)
            loop.save_run(run_path, run)
        host = host or NativeCodexHost()
        for _ in range(max_actions):
            if run['state'] in {'ACCEPTED', 'BLOCKED'}:
                break
            action = run['next_action']
            try:
                packet = build_from_paths(asset, edit, run_path)
                run = loop.load_run(run_path)
                action = packet['action']
                step = evidence_dir / f"{run['iteration']:04d}-{action}"
                # Prevalidate approved source, Mask, and prior repair receipt
                # BEFORE any native Host call, so a broken repair cannot spend
                # another generation and only then discover invalid lineage.
                if action != 'visual_qa' and is_strict_native_run(run):
                    preflight_native_strict(run, packet)
                # Any partial step is ambiguous: never rerun a paid/tool action.
                step.mkdir(parents=True, exist_ok=False)
                json_new(step / 'packet.json', packet)
                reviewer = action == 'visual_qa'
                if reviewer:
                    receipt = run['current_receipt']
                    if receipt_digest(receipt) != receipt['receipt_id']:
                        raise ValidationError('invalid receipt')
                    # The generation receipt, including repair target, is authoritative.
                    if packet['input_bindings'] != receipt['input_bindings']:
                        # QA packets normally contain preflight inputs, not repair target.
                        from artifact_integrity import packet_digest
                        packet['input_bindings'] = receipt['input_bindings']
                        packet['packet_id'] = packet_digest(packet)
                        json_new(step / 'critic-packet.json', packet)
                value, attestation, transcript = host.execute(packet, reviewer=reviewer)
                if loop.load_run(run_path) != run:
                    # Another state-machine client changed the run while the host worked.
                    run = loop.load_run(run_path)
                    raise ValidationError('concurrent run mutation requires reconciliation')
                write_new(step / 'events.jsonl', transcript)
                if reviewer:
                    json_new(step / 'attestation.json', attestation)
                    value = validate_critic(value, run['required_hard_gates'])
                    qa = {**value, 'document_type': 'qa_report', 'schema_version': 1,
                          'report_id': f"QA_{run['run_id']}_{run['iteration']}",
                          'asset_id': run['asset_id'], 'request_id': run['request_id'],
                          'run_id': run['run_id'], 'iteration': run['iteration'],
                          'receipt_id': receipt['receipt_id'], 'result_sha256': receipt['result_sha256']}
                    qa['gates'] = [{**g, 'severity': 'hard'} for g in value['gates']]
                    qa_path = step / 'qa.toml'
                    write_new(qa_path, qa_toml(qa))
                    run = loop.apply_qa_from_path(run, qa_path)
                else:
                    result_path = step / 'generated.png'
                    if is_strict_native_run(run):
                        # Native model bytes and original events remain independent.
                        # Derived output is the only image sent to final Visual QA.
                        write_new(step / 'native-generated.png', value)
                        proof = compose_native_generation(run, packet, step)
                        attestation = {**attestation, 'postprocess': proof}
                    else:
                        write_new(result_path, value)
                    json_new(step / 'attestation.json', attestation)
                    run = loop._record_auditable_generation(
                        run, str(result_path), packet=packet,
                        receipt_path=step / 'receipt.json', host_attestation=attestation)
                loop.save_run(run_path, run)
            except (OSError, ValueError, KeyError, TypeError, ValidationError):
                # Never persist exception strings: provider output may contain secrets.
                if run['state'] == 'ACCEPTED':
                    raise ValidationError('concurrent acceptance requires reconciliation') from None
                run = loop.mark_blocked(run, reason_code=(
                    'visual_inspection_unavailable' if action == 'visual_qa' else 'host_native_imagegen_failed'),
                    action=action, message='Host step failed or conflicting partial evidence; reconciliation required.',
                    retryable=False)
                loop.save_run(run_path, run)
                break
        if run['state'] == 'ACCEPTED':
            report = evidence_dir / 'deliverable.json'
            deliverable = {'run_id': run['run_id'], 'result': run['current_receipt']['result'],
                           'receipt_id': run['current_receipt']['receipt_id'],
                           'scope': 'non-commercial deliverable; no Master promotion or Steam approval'}
            try:
                if report.exists():
                    if json.loads(report.read_text()) != deliverable:
                        raise ValidationError('conflicting deliverable')
                else:
                    json_new(report, deliverable)
            except (OSError, ValueError):
                # ACCEPTED is terminal in the state machine; report a reconciliation
                # failure without rewriting its acceptance or existing delivery files.
                return {'run_id': run['run_id'], 'state': 'ERROR',
                        'next_action': 'reconcile_delivery', 'result': run.get('current_result_path'),
                        'blocker': {'message': 'Delivery evidence conflict; reconciliation required.'}}
        return {'run_id': run['run_id'], 'state': run['state'], 'next_action': run['next_action'],
                'result': run.get('current_result_path'), 'blocker': run.get('blocker')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    status = commands.add_parser('status')
    status.add_argument('--run', required=True, type=Path)
    run = commands.add_parser('run')
    for name in ('asset', 'edit', 'workspace-root', 'run'):
        run.add_argument('--' + name, required=True, type=Path)
    run.add_argument('--codex')
    run.add_argument('--max-actions', type=int, default=8)
    run.add_argument('--resume', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'status':
            value = loop.load_run(args.run)
            result = {k: value.get(k) for k in ('run_id', 'state', 'next_action', 'blocker')}
        else:
            result = drive(args.asset, args.edit, args.workspace_root, args.run,
                           resume=args.resume, max_actions=args.max_actions,
                           host=NativeCodexHost(args.codex))
        print(json.dumps(result))
        # A bounded nonterminal pause MUST NOT be a successful production exit.
        if args.command == 'status':
            return 0  # read-only observation, not release certification
        if result['state'] == 'ACCEPTED':
            return 0
        if result['state'] in {'BLOCKED', 'ERROR'}:
            return 2
        return 3  # READY/QA_PENDING/REPAIR_READY/REGENERATE_READY
    except (OSError, ValueError, ValidationError):
        print(json.dumps({'state': 'ERROR', 'message': 'Invalid invocation or unreadable run; no host retry.'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

