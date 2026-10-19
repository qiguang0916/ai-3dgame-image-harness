"""Subscription-only native Codex host; no API fallback."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from artifact_integrity import packet_digest, resolve_in_workspace, sha256_file, sha256_bytes
from runtime_preflight import validate_image_file
from validate_project import ValidationError

DEFAULT_CODEX = '/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex'


def clean_environment():
    return {k: v for k, v in os.environ.items() if k in {
        'HOME', 'PATH', 'TMPDIR', 'LANG', 'LC_ALL', 'CODEX_HOME', 'USER', 'LOGNAME'
    }}


def image_tool_calls(transcript):
    """Count structured host-native image events when the CLI exposes them.

    Codex CLI 0.163 may NOT expose an image_generation_call in --json. A
    distinct successful cp from CODEX_HOME/generated_images is also acceptable
    provenance for this subscription host, provided the source exists and its
    SHA256 equals the persisted result. This is NOT cryptographic model proof.
    """
    calls = set()
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        item = event.get('item') or {}
        if not isinstance(item, dict) or event.get('type') != 'item.completed':
            continue
        native = item.get('type') in {'image_generation_call', 'image_gen_call'}
        mcp = item.get('type') == 'mcp_tool_call' and item.get('tool') in {
            'imagegen', 'image_gen.imagegen'
        }
        if native or mcp:
            if not item.get('id'):
                raise ValidationError('image tool event lacks identity')
            calls.add(item['id'])
    return len(calls)


def native_generated_source(transcript, output, home):
    """Find a verified native source in completed CLI copy evidence.

    The local Codex built-in image_gen writes the source PNG under
    CODEX_HOME/generated_images and typically copies it with a successful
    command_execution cp action. Reject path-only messages and failed copies.
    """
    source_root = Path(home).expanduser().resolve() / 'generated_images'
    target_digest = sha256_file(output)
    matches = []
    for line in transcript.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        item = event.get('item') or {}
        if event.get('type') != 'item.completed' or not isinstance(item, dict):
            continue
        if item.get('type') != 'command_execution' or item.get('exit_code') != 0:
            continue
        cmd = str(item.get('command', ''))
        if 'generated_images/' not in cmd or not re.search(r'(?<![A-Za-z0-9_])cp\s', cmd):
            continue
        for raw in re.findall(r'/[^\s"\x27`<>\\]*generated_images/[^\s"\x27`<>\\]+\.png', cmd):
            path = Path(raw).expanduser().resolve()
            if (path.is_relative_to(source_root) and path.is_file()
                    and sha256_file(path) == target_digest and path not in matches):
                matches.append(path)
    if len(matches) != 1:
        raise ValidationError('native generated_images copy proof missing/ambiguous or SHA mismatch')
    return matches[0]


def validate_critic(value, required):
    statuses = {'PASS', 'PASS_WITH_NOTES', 'REPAIR_MINOR', 'REGENERATE_MAJOR', 'BLOCKED'}
    if not isinstance(value, dict) or value.get('status') not in statuses:
        raise ValidationError('invalid critic status')
    if not isinstance(value.get('summary'), str) or not value['summary'].strip():
        raise ValidationError('missing critic summary')
    directives = value.get('repair_directives')
    if not isinstance(directives, list) or any(not isinstance(x, str) or not x.strip() for x in directives):
        raise ValidationError('invalid critic directives')
    gates = value.get('gates')
    if not isinstance(gates, list) or any(not isinstance(g, dict) for g in gates):
        raise ValidationError('invalid critic gates')
    names = [g.get('name') for g in gates]
    if any(not isinstance(n, str) for n in names) or len(names) != len(set(names)) or set(names) != set(required):
        raise ValidationError('critic must cover exactly required gates')
    for gate in gates:
        if gate.get('status') not in {'PASS', 'FAIL', 'NOT_VERIFIABLE'}:
            raise ValidationError('invalid gate status')
        for key in ('note', 'inspection_method', 'observation'):
            if not isinstance(gate.get(key), str) or len(gate[key].strip()) < 12:
                raise ValidationError('critic needs concrete pixel evidence')
    passed = all(g['status'] == 'PASS' for g in gates)
    if (value['status'] in {'PASS', 'PASS_WITH_NOTES'}) != passed:
        raise ValidationError('critic status contradicts gates')
    if value['status'] in {'REPAIR_MINOR', 'REGENERATE_MAJOR'} and not directives:
        raise ValidationError('repair requires directives')
    if len(gates) > 1 and len({g['observation'] for g in gates}) == 1:
        raise ValidationError('duplicated generic pixel evidence')
    return value


class NativeCodexHost:
    def __init__(self, codex=None, timeout=600):
        if not 30 <= timeout <= 1800:
            raise ValidationError('timeout must be 30..1800 seconds')
        self.codex = str(Path(codex or shutil.which('codex') or DEFAULT_CODEX).expanduser().resolve())
        self.timeout = timeout
        self.env = clean_environment()

    def _call(self, argv, **kwargs):
        try:
            result = subprocess.run([self.codex, *argv], env=self.env,
                                    capture_output=True, timeout=self.timeout, **kwargs)
        except (OSError, subprocess.TimeoutExpired):
            raise ValidationError('native Codex unavailable or timed out') from None
        if result.returncode:
            raise ValidationError('native Codex failed; diagnostics withheld')
        return result

    def execute(self, packet, reviewer=False):
        if packet.get('packet_id') != packet_digest(packet):
            raise ValidationError('invalid packet digest')
        login = self._call(['login', 'status'])
        if b'Logged in using ChatGPT' not in login.stdout + login.stderr:
            raise ValidationError('ChatGPT subscription authentication required')
        bindings = list(packet.get('input_bindings', []))
        if reviewer:
            bindings.append(packet['result_binding'])
        if len(bindings) > 8:
            raise ValidationError('at most eight attachments allowed')
        with tempfile.TemporaryDirectory(prefix='native-codex-host-') as directory:
            stage = Path(directory)
            images, originals = [], []
            for index, binding in enumerate(bindings):
                source = resolve_in_workspace(packet['workspace_root'], binding['path'])
                if sha256_file(source) != binding['sha256'] or not validate_image_file(source)[0]:
                    raise ValidationError('input SHA or PNG mismatch')
                target = stage / f'input-{index}.png'
                shutil.copyfile(source, target)
                originals.append((source, target, binding['sha256']))
                images.append(target)
            technical_precheck = None
            if reviewer and 'image.technical_output' in packet.get('required_hard_gates', []):
                from asset_report import inspect_output
                output_spec = packet.get('technical_output')
                if not isinstance(output_spec, dict) or not (
                    {'expected_size', 'require_transparency'} & set(output_spec)
                ):
                    raise ValidationError('critic technical gate has no bound output contract')
                # Last input is the SHA-matched candidate image. This result
                # comes from deterministic decoded pixels, not a Host claim.
                technical_precheck = inspect_output(images[-1], output_spec)
                if technical_precheck['sha256'] != packet['result_binding']['sha256']:
                    raise ValidationError('technical precheck image not bound to receipt result')
            (stage / 'packet.json').write_text(json.dumps(packet), encoding='utf-8')
            staged_packet_sha = sha256_file(stage / 'packet.json')
            final = stage / 'final.json'
            output = stage / 'outputs' / 'generated.png'
            if not reviewer:
                output.parent.mkdir()
            argv = ['exec', '--ephemeral', '--ignore-user-config', '--json', '-C', str(stage),
                    '-s', 'read-only' if reviewer else 'workspace-write', '--skip-git-repo-check']
            for image in images:
                argv.extend(['-i', str(image)])
            argv.extend(['-o', str(final), '-'])
            if reviewer:
                prompt = ('Read packet.json. Inspect actual attached pixels; last image is candidate, '
                          'earlier images are SHA-bound sources in binding order. Never invoke image_gen. '
                          'Return ONLY JSON: status, summary, repair_directives, gates. '
                          'EXACT required_hard_gates, each with name,status (PASS/FAIL/NOT_VERIFIABLE), '
                          'note,inspection_method,observation: distinct concrete pixel evidence. '
                          'Status PASS/PASS_WITH_NOTES/REPAIR_MINOR/REGENERATE_MAJOR/BLOCKED. '
                          'Unverifiable gates cannot PASS. No human, rights, or Steam approval claims.')
                if technical_precheck is not None:
                    prompt += (
                        ' DIGEST-BOUND TECHNICAL IMAGE MEASUREMENT from local verified '
                        'Pillow pixels (NOT a user assertion, NOT an artistic judgment): '
                        f"result_sha256={technical_precheck['sha256']} "
                        f"status={technical_precheck['status']} "
                        f"width={technical_precheck['width']} height={technical_precheck['height']} "
                        f"has_transparency={technical_precheck['has_transparency']} "
                        f"failures={json.dumps(technical_precheck['failures'])}. "
                        'For image.technical_output use the measured status PASS/FAIL, '
                        'citing this verified SHA and measurement method. '
                        'A technical PASS does NOT certify subjective geometry, style, '
                        'license, rights or any other gate. Inspect other visual gates '
                        'independently; mark NOT_VERIFIABLE when actual pixels unavailable.'
                    )
            else:
                prompt = ('Read packet.json; follow its prompt, delta and bindings. Attached input-N.png '
                          'correspond to input_bindings in order. Invoke built-in native image_gen.imagegen '
                          'EXACTLY ONCE. No API, CLI generator, local model or provider fallback. '
                          'If unavailable stop. Copy actual native PNG from CODEX_HOME/generated_images '
                          'to outputs/generated.png using cp. Include absolute native source path in final. '
                          'Never modify inputs or create a substitute image.')
            transcript = self._call(argv, input=prompt.encode()).stdout
            if sha256_file(stage / 'packet.json') != staged_packet_sha:
                raise ValidationError('host changed staged packet')
            for source, target, digest in originals:
                if sha256_file(source) != digest or sha256_file(target) != digest:
                    raise ValidationError('host changed input')
            evidence = {'event_transcript_sha256': sha256_bytes(transcript),
                        'backend': 'native_codex_chatgpt', 'model_identity_verified': False,
                        'packet_id': packet['packet_id'],
                        'input_sha256': [binding['sha256'] for binding in bindings]}
            if reviewer:
                if image_tool_calls(transcript):
                    raise ValidationError('critic invoked image tool')
                answer = validate_critic(json.loads(final.read_text()),
                                         packet['required_hard_gates'])
                if technical_precheck is not None:
                    actual = next((gate for gate in answer['gates']
                                   if gate['name'] == 'image.technical_output'), None)
                    if actual is None or (
                        actual['status'] == 'PASS' and technical_precheck['status'] != 'PASS'
                    ):
                        raise ValidationError('critic technical PASS conflicts with actual pixels')
                    evidence['technical_precheck'] = {
                        key: technical_precheck[key]
                        for key in ('sha256', 'status', 'width', 'height',
                                    'has_transparency', 'failures')
                    }
                return answer, evidence, transcript
            structured_calls = image_tool_calls(transcript)
            if structured_calls > 1:
                raise ValidationError('more than one native image tool invocation detected')
            if output.is_symlink() or not validate_image_file(output)[0]:
                raise ValidationError('invalid native output PNG')
            home = Path(self.env.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser().resolve()
            native = native_generated_source(transcript, output, home)
            evidence.update(
                native_provenance="completed_native_generated_images_copy_and_matching_sha256",
                structured_tool_call_count=structured_calls,
                structured_event_missing=(structured_calls == 0),
                native_artifact_is_model_attestation=False,
            )
            evidence.update(native_source=str(native), result_sha256=sha256_file(output))
            return output.read_bytes(), evidence, transcript
