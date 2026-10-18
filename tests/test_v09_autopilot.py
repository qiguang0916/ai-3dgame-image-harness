"""Offline synthetic host tests; these are not real imagegen evidence."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cli
import execution_loop as loop
import production_autopilot as autopilot
from native_codex_host import NativeCodexHost, clean_environment, validate_critic
import test_v06_integration as fixtures
import test_v06_upgrade as bootstrap_fixtures


class StubHost:
    def __init__(self, image, statuses=()):
        self.image, self.statuses, self.actions = image, iter(statuses), []

    def execute(self, packet, reviewer=False):
        self.actions.append(packet['action'])
        if not reviewer:
            return self.image, {'host': 'synthetic offline stub'}, b'{"fixture":true}\n'
        status = next(self.statuses, 'PASS')
        gates = [{'name': name, 'status': 'PASS', 'note': 'Synthetic comparison evidence only.',
                  'inspection_method': 'Synthetic fixture pixel comparison',
                  'observation': 'Synthetic fixture visible match for ' + name}
                 for name in packet['required_hard_gates']]
        if status != 'PASS':
            gates[0]['status'] = 'FAIL'
        return {'status': status, 'summary': 'Synthetic fixture QA result',
                'repair_directives': [] if status == 'PASS' else ['Fix synthetic fixture mismatch'],
                'gates': gates}, {'host': 'synthetic critic'}, b'{"fixture":true}\n'


class AutopilotTests(unittest.TestCase):
    def test_native_adapter_provenance_and_fixed_argv(self):
        from artifact_integrity import packet_digest
        for mode in ('valid', 'native_copy_only', 'no_provenance', 'failed_copy', 'two_calls', 'invalid_json', 'input_changed'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                a, e, r, host = self.fixture(root)
                import next_action
                packet = next_action.build_from_paths(a, e, r)
                native = root / 'codex-home' / 'generated_images' / 'session' / 'native.png'
                native.parent.mkdir(parents=True)
                native.write_bytes(host.image)
                calls = []

                def fake_run(argv, **kwargs):
                    calls.append(argv)
                    self.assertNotIn('OPENAI_API_KEY', kwargs['env'])
                    self.assertNotIn('shell', kwargs)
                    if argv[1:] == ['login', 'status']:
                        return subprocess.CompletedProcess(argv, 0, b'', b'Logged in using ChatGPT')
                    stage = Path(argv[argv.index('-C') + 1])
                    self.assertIn('--ephemeral', argv)
                    self.assertIn('--ignore-user-config', argv)
                    self.assertEqual(argv[argv.index('-s') + 1], 'workspace-write')
                    self.assertEqual(len(list(stage.glob('input-*.png'))), len(packet['input_bindings']))
                    (stage / 'outputs' / 'generated.png').write_bytes(host.image)
                    if mode == 'input_changed':
                        (stage / 'input-0.png').write_bytes(b'changed')
                    events = [] if mode == 'native_copy_only' else [
                        {'type': 'item.completed', 'item': {'id': 'one', 'type': 'image_generation_call'}}
                    ]
                    if mode == 'two_calls':
                        events.append({'type': 'item.completed', 'item': {'id': 'two', 'type': 'image_generation_call'}})
                    if mode != 'no_provenance':
                        events.append({
                            'type': 'item.completed',
                            'item': {'type': 'command_execution', 'id': 'copier',
                                     'status': 'completed',
                                     'exit_code': 1 if mode == 'failed_copy' else 0,
                                     'command': f"/bin/zsh -lc 'cp {native} outputs/generated.png'"}
                        })
                    data = b'invalid JSON' if mode == 'invalid_json' else ('\n'.join(json.dumps(x) for x in events)).encode()
                    return subprocess.CompletedProcess(argv, 0, data, b'')

                with patch.dict(os.environ, {'CODEX_HOME': str(root / 'codex-home'), 'OPENAI_API_KEY': 'SECRET_SENTINEL'}), patch('native_codex_host.subprocess.run', side_effect=fake_run):
                    adapter = NativeCodexHost('/fake/codex')
                    if mode in ('valid', 'native_copy_only'):
                        image, evidence, transcript = adapter.execute(packet)
                        self.assertEqual(image, host.image)
                        self.assertEqual(evidence['native_source'], str(native.resolve()))
                        self.assertEqual(len(calls), 2)
                        self.assertEqual(evidence['structured_event_missing'], mode == 'native_copy_only')
                    else:
                        with self.assertRaises(ValueError):
                            adapter.execute(packet)

    def test_native_auth_timeout_and_invalid_packet(self):
        from artifact_integrity import packet_digest
        packet = {'input_bindings': []}
        packet['packet_id'] = packet_digest(packet)
        with patch('native_codex_host.subprocess.run', return_value=subprocess.CompletedProcess([], 0, b'API key login', b'')):
            with self.assertRaises(ValueError):
                NativeCodexHost('/fake/codex').execute(packet)
        with patch('native_codex_host.subprocess.run', side_effect=subprocess.TimeoutExpired([], 30)):
            with self.assertRaises(ValueError):
                NativeCodexHost('/fake/codex').execute(packet)
        with self.assertRaises(ValueError):
            NativeCodexHost('/fake/codex').execute({})

    def test_native_critic_readonly_json_and_tool_rejection(self):
        import next_action
        for mode in ('valid', 'invalid_json', 'forbidden_tool'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                a, e, r, host = self.fixture(root)
                autopilot.drive(a, e, root, r, resume=True, max_actions=1, host=host)
                packet = next_action.build_from_paths(a, e, r)

                def fake_run(argv, **kwargs):
                    if argv[1:] == ['login', 'status']:
                        return subprocess.CompletedProcess(argv, 0, b'Logged in using ChatGPT', b'')
                    self.assertEqual(argv[argv.index('-s') + 1], 'read-only')
                    stage = Path(argv[argv.index('-C') + 1])
                    attached = [argv[i + 1] for i, x in enumerate(argv) if x == '-i']
                    self.assertEqual(Path(attached[-1]).read_bytes(), host.image)
                    qa, _, _ = host.execute(packet, reviewer=True)
                    final = Path(argv[argv.index('-o') + 1])
                    final.write_text('invalid JSON' if mode == 'invalid_json' else json.dumps(qa))
                    event = {'type': 'item.completed', 'item': {'id': 'bad', 'type': 'image_generation_call'}}
                    return subprocess.CompletedProcess(argv, 0, json.dumps(event if mode == 'forbidden_tool' else {}).encode(), b'')

                with patch('native_codex_host.subprocess.run', side_effect=fake_run):
                    adapter = NativeCodexHost('/fake/codex')
                    if mode == 'valid':
                        self.assertEqual(adapter.execute(packet, reviewer=True)[0]['status'], 'PASS')
                    else:
                        with self.assertRaises(ValueError):
                            adapter.execute(packet, reviewer=True)

    def test_bootstrap_create(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, e, r, host = self.fixture(root)
            r.unlink()
            a.write_text(bootstrap_fixtures.BOOTSTRAP_ASSET)
            e.write_text(bootstrap_fixtures.BOOTSTRAP_EDIT)
            result = autopilot.drive(a, e, root, r, host=host)
            self.assertEqual(result['state'], 'ACCEPTED')
            self.assertEqual(host.actions[0], 'imagegen_generate')

    def fixture(self, root):
        a, e, r, _ = fixtures.V06IntegrationTests()._init(root)
        return a, e, r, StubHost((root / 'master.png').read_bytes())

    def test_edit_resume_deliver_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, e, r, host = self.fixture(root)
            r.unlink()
            first = autopilot.drive(a, e, root, r, max_actions=1, host=host)
            self.assertEqual(first['state'], 'QA_PENDING')
            result = autopilot.drive(a, e, root, r, resume=True, host=host)
            self.assertEqual(result['state'], 'ACCEPTED')
            receipts = list(root.rglob('receipt.json'))
            original = receipts[0].read_bytes()
            autopilot.drive(a, e, root, r, resume=True, host=host)
            self.assertEqual(receipts[0].read_bytes(), original)
            self.assertEqual(len(host.actions), 2)
            with self.assertRaises(ValueError):
                autopilot.drive(a, e, root, r, host=host)

    def test_repair_and_regeneration(self):
        for status in ('REPAIR_MINOR', 'REGENERATE_MAJOR'):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                a, e, r, host = self.fixture(root)
                host.statuses = iter([status, 'PASS'])
                result = autopilot.drive(a, e, root, r, resume=True, host=host)
                self.assertEqual(result['state'], 'ACCEPTED')
                self.assertEqual(len(list(root.rglob('receipt.json'))), 2)
                self.assertEqual(len(host.actions), 4)

    def test_partial_output_blocks_without_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, e, r, host = self.fixture(root)
            step = root / 'run.json.production' / '0000-imagegen_edit'
            step.mkdir(parents=True)
            output = step / 'generated.png'
            output.write_bytes(b'partial')
            result = autopilot.drive(a, e, root, r, resume=True, host=host)
            self.assertEqual(result['state'], 'BLOCKED')
            self.assertEqual(host.actions, [])
            self.assertEqual(output.read_bytes(), b'partial')

    def test_host_failure_does_not_leak_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, e, r, host = self.fixture(root)
            with patch.object(host, 'execute', side_effect=ValueError('SECRET_SENTINEL')):
                result = autopilot.drive(a, e, root, r, resume=True, host=host)
            self.assertEqual(result['state'], 'BLOCKED')
            self.assertNotIn('SECRET_SENTINEL', r.read_text())
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'SECRET_SENTINEL'}):
                self.assertNotIn('OPENAI_API_KEY', clean_environment())

    def test_invalid_critic_and_receipt_block(self):
        for invalid in ('critic', 'receipt'):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                a, e, r, host = self.fixture(root)
                autopilot.drive(a, e, root, r, resume=True, max_actions=1, host=host)
                if invalid == 'receipt':
                    run = loop.load_run(r)
                    run['current_receipt']['result_sha256'] = '0' * 64
                    loop.save_run(r, run)
                else:
                    host.execute = lambda *a, **kw: ({'status': 'PASS'}, {}, b'{}\n')
                result = autopilot.drive(a, e, root, r, resume=True, host=host)
                self.assertEqual(result['state'], 'BLOCKED')

    def test_critic_rejects_missing_duplicate_and_generic_gates(self):
        for gates in ([], [{'name': 'a'}, {'name': 'a'}]):
            with self.assertRaises(ValueError):
                validate_critic({'status': 'PASS', 'summary': 'Fixture summary',
                                 'repair_directives': [], 'gates': gates}, ['a'])
        with self.assertRaises(ValueError):
            NativeCodexHost(timeout=1)

    def test_cli_nonterminal_pause_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, e, r, host = self.fixture(root)
            r.unlink()
            with patch('production_autopilot.NativeCodexHost', return_value=host), contextlib.redirect_stdout(io.StringIO()) as out:
                status = cli.main(['autopilot', 'run', '--asset', str(a), '--edit', str(e),
                                   '--workspace-root', str(root), '--run', str(r), '--max-actions', '1'])
            self.assertEqual(3, status)
            self.assertEqual('QA_PENDING', json.loads(out.getvalue())['state'])
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main(['autopilot', 'status', '--run', str(r)]), 0)
            self.assertEqual('QA_PENDING', json.loads(out.getvalue())['state'])

    def test_cli_status_and_blocked_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, e, r, host = self.fixture(root)
            with patch('production_autopilot.NativeCodexHost', return_value=host), contextlib.redirect_stdout(io.StringIO()) as out:
                code = cli.main(['autopilot', 'run', '--asset', str(a), '--edit', str(e),
                                 '--workspace-root', str(root), '--run', str(r), '--resume'])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.getvalue())['state'], 'ACCEPTED')
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main(['autopilot', 'status', '--run', str(r)]), 0)
            self.assertEqual(json.loads(out.getvalue())['state'], 'ACCEPTED')
