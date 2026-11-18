#!/usr/bin/env python
"""Additive, receipted integration for the existing RHEL EDA store (Python 2.6+)."""
from __future__ import print_function
import os
import sys
import json
import hashlib
import subprocess
import time
import tempfile
from optparse import OptionParser

sys.dont_write_bytecode = True

BEGIN = '# BEGIN MANAGED SKILL-ANALOG'
END = '# END MANAGED SKILL-ANALOG'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_bytes(path):
    with open(path, 'rb') as handle:
        return handle.read()


def supported_mode(mode):
    # Windows stat/chmod cannot represent POSIX execute/group permission bits.
    # Linux receipts retain all original permission bits.
    if os.name == 'nt':
        return 438 if mode & 128 else 292
    return mode


def shell_quote(value):
    return "'" + value.replace("'", "'\"'\"'") + "'"


def sync_directory(path):
    if os.name == 'nt':
        return
    handle = os.open(path, os.O_RDONLY)
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


def snapshot(path):
    if os.path.islink(path):
        return {'kind': 'symlink', 'target': os.readlink(path)}
    if os.path.isfile(path):
        data = read_bytes(path)
        return {'kind': 'file', 'sha256': digest(data), 'mode': os.stat(path).st_mode & 511}
    if os.path.lexists(path):
        raise ValueError('Refusing non-file target: ' + path)
    return {'kind': 'absent'}


def atomic(path, data, mode):
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    temporary = path + '.skill-analog-tmp'
    if os.path.lexists(temporary):
        raise ValueError('Stale temporary path: ' + temporary)
    created = False
    try:
        handle = os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode), 'wb')
        created = True
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.chmod(temporary, mode)
        if hasattr(os, 'replace'):
            os.replace(temporary, path)
        else:
            os.rename(temporary, path)
        sync_directory(parent)
    finally:
        if created and os.path.isfile(temporary):
            os.unlink(temporary)


class Installer(object):
    def __init__(self, root, user_home):
        self.root = os.path.realpath(root)
        self.user_home = os.path.abspath(user_home)
        self.library = os.path.join(self.root, 'references', 'SKILL-ANALOG')
        receipt_base = os.path.join(self.root, 'backups', 'skill-analog')
        if not os.path.isdir(receipt_base):
            os.makedirs(receipt_base)
        self.receipt_dir = tempfile.mkdtemp(prefix=
            time.strftime('%Y%m%dT%H%M%S', time.gmtime()) + '-%s-' % os.getpid(),
            dir=receipt_base)
        self.receipt = {'schema': 'skill-analog-install.v1', 'root': self.root,
                        'library': self.library, 'operations': [], 'complete': False,
                        'project_metadata_rollback': 'retained intentionally; additive project files are user data, not discovery configuration'}
        self.save()

    def save(self):
        data = json.dumps(self.receipt, indent=2, sort_keys=True).encode('utf-8')
        atomic(os.path.join(self.receipt_dir, 'receipt.json'), data, 384)

    def change(self, path, data=None, target=None, mode=420):
        path = os.path.abspath(path)
        before = snapshot(path)
        after = {'kind': 'symlink', 'target': target} if target is not None else {
            'kind': 'file', 'sha256': digest(data), 'mode': supported_mode(mode)}
        if before == after:
            return
        # Intent and backup are durable before changing the target.
        op = {'path': path, 'before': before, 'after': after, 'applied': False}
        if before['kind'] == 'file':
            backup = os.path.join(self.receipt_dir, '%04d.original' % len(self.receipt['operations']))
            backup_data = read_bytes(path)
            if digest(backup_data) != before['sha256']:
                raise ValueError('Target changed while backing up: ' + path)
            atomic(backup, backup_data, 384)
            op['backup'] = backup
        self.receipt['operations'].append(op)
        self.save()
        if snapshot(path) != before:
            raise ValueError('Target changed during installation; preserved: ' + path)
        if target is not None:
            if before['kind'] != 'absent':
                raise ValueError('Refusing to replace an existing discovery link: ' + path)
            parent = os.path.dirname(path)
            if not os.path.isdir(parent):
                os.makedirs(parent)
            os.symlink(target, path)
        else:
            if before['kind'] == 'symlink':
                raise ValueError('Refusing to overwrite an existing symlink: ' + path)
            atomic(path, data, mode)
        op['applied'] = True
        self.save()

    def integrate(self):
        # Prepare and validate all configuration changes before the first target mutation.
        changes = []
        skill = os.path.join(self.library, 'skills', 'analog-design')
        native_skill = os.path.join(self.user_home, '.agents', 'skills', 'analog-design')
        if not os.path.isfile(os.path.join(skill, 'SKILL.md')):
            raise ValueError('Native skill entry point is missing: ' + skill)
        if os.path.lexists(native_skill) and (not os.path.islink(native_skill) or os.path.realpath(native_skill) != os.path.realpath(skill)):
            raise ValueError('Existing native skill needs review: ' + native_skill)
        if not os.path.lexists(native_skill):
            changes.append((native_skill, None, skill, 420))
        codex_home = os.path.join(self.root, 'apps', 'codex', 'data')
        override = os.path.join(codex_home, 'AGENTS.override.md')
        global_path = override if os.path.isfile(override) and os.path.getsize(override) else os.path.join(codex_home, 'AGENTS.md')
        guidance = os.path.join(self.library, 'integration', 'codex-user-AGENTS.md')
        guidance_text = read_bytes(guidance).decode('utf-8')
        if not os.path.lexists(global_path):
            changes.append((global_path, None, guidance, 420))
        elif os.path.islink(global_path):
            if os.path.realpath(global_path) != os.path.realpath(guidance):
                raise ValueError('Existing global instructions symlink needs review: ' + global_path)
        else:
            original = read_bytes(global_path).decode('utf-8')
            if not os.path.isfile(global_path):
                raise ValueError('Global instruction target is not a regular file: ' + global_path)
            block = BEGIN + '\n' + guidance_text + '\n' + END
            if BEGIN in original or END in original:
                if original.count(BEGIN) != 1 or original.count(END) != 1:
                    raise ValueError('Malformed managed guidance block')
                start, finish = original.index(BEGIN), original.index(END) + len(END)
                if original.index(END) < start:
                    raise ValueError('Managed guidance markers out of order')
                updated = original[:start] + block + original[finish:]
            else:
                updated = original + '\n\n' + block + '\n'
            changes.append((global_path, updated.encode('utf-8'), None, os.stat(global_path).st_mode & 511))

        eda = os.path.join(self.root, 'admin', 'bin', 'eda')
        if os.path.islink(eda) or not os.path.isfile(eda):
            raise ValueError('EDA launcher must be a regular file: ' + eda)
        original = read_bytes(eda).decode('utf-8')
        marker = '# SKILL-ANALOG project metadata'
        anchor = "    printf 'Created: %s\\n' \"$project\""
        if marker not in original:
            if original.count(anchor) != 1:
                raise ValueError('EDA launcher changed; cannot safely patch creation step')
            addition = ('    ' + marker + '\n'
                '    if [[ "$kind" == cadence ]]; then\n'
                '        python "$eda_root/references/SKILL-ANALOG/tools/analogctl.py" init "$project"\n'
                '    fi\n')
            changes.append((eda, original.replace(anchor, addition + anchor).encode('utf-8'), None, os.stat(eda).st_mode & 511))
        elif original.count(marker) != 1 or 'python "$eda_root/references/SKILL-ANALOG/tools/analogctl.py" init "$project"' not in original:
            raise ValueError('Existing EDA integration needs review')

        cadence_new = ('#!/usr/bin/env bash\nset -euo pipefail\n'
            'exec ' + shell_quote(self.root + '/admin/bin/eda') + ' new "$@"\n')
        changes.append((os.path.join(self.user_home, 'bin', 'cadence-new'), cadence_new.encode('utf-8'), None, 493))
        cadence = ('#!/usr/bin/env bash\nset -euo pipefail\n'
            'if [[ $# -gt 0 ]]; then exec ' + shell_quote(self.root + '/admin/bin/eda') + ' open "$@"; fi\n'
            'project="$(python ' + shell_quote(self.root + '/references/SKILL-ANALOG/tools/analogctl.py') +
            ' locate "$PWD" | PYTHONIOENCODING=utf-8 python -c ' + shell_quote(
                'import json,sys; value=json.load(sys.stdin); '
                'sys.stdout.write(value["project_root"]) if value.get("ok") else '
                'sys.exit(value.get("error", "Cannot identify project"))') + ')"\n'
            '[[ -f "$project/cds.lib" ]] || { printf "Project has no cds.lib: %s\\n" "$project" >&2; exit 1; }\n'
            'if [[ -x "$project/scripts/run-virtuoso.sh" ]]; then\n'
            '    exec "$project/scripts/run-virtuoso.sh"\n'
            'fi\n'
            'source "$HOME/cadence/env.sh"\n'
            'mkdir -p "$project/sim/logs"\n'
            'cd "$project"\n'
            'exec /opt/IC617/bin/virtuoso -log "$project/sim/logs/virtuoso.log"\n')
        changes.append((os.path.join(self.user_home, 'bin', 'cadence'), cadence.encode('utf-8'), None, 493))
        for path, data, target, mode in changes:
            before = snapshot(path)
            parent = os.path.dirname(path)
            while not os.path.exists(parent):
                parent = os.path.dirname(parent)
            if not os.path.isdir(parent) or not os.access(parent, os.W_OK | os.X_OK):
                raise ValueError('Configuration parent is not writable: ' + parent)
            if target is None and before['kind'] == 'symlink':
                raise ValueError('Existing configuration symlink needs review: ' + path)
            if target is not None and before['kind'] not in ('absent', 'symlink'):
                raise ValueError('Existing discovery target needs review: ' + path)
            if os.path.lexists(path + '.skill-analog-tmp'):
                raise ValueError('Stale temporary path needs review: ' + path + '.skill-analog-tmp')
        for path, data, target, mode in changes:
            self.change(path, data=data, target=target, mode=mode)

        # Register existing catalog projects without changing any design files.
        catalog = os.path.join(self.root, 'projects', 'cadence')
        initialized = []
        self.receipt['projects_initialized'] = initialized
        if os.path.isdir(catalog):
            for name in sorted(os.listdir(catalog)):
                project = os.path.join(catalog, name)
                if not os.path.isdir(project) or not os.path.isfile(os.path.join(project, 'cds.lib')):
                    continue
                process = subprocess.Popen([sys.executable,
                    os.path.join(self.library, 'tools', 'analogctl.py'), 'init', project], stdout=subprocess.PIPE)
                output = process.communicate()[0]
                if process.returncode:
                    raise ValueError('Project metadata initialization failed: ' + project)
                initialized.append(json.loads(output.decode('utf-8')))
                self.save()
        self.receipt['projects_initialized'] = initialized
        self.save()

        self.receipt['complete'] = True
        self.save()
        return self.receipt_dir


def rollback(receipt_path):
    receipt = json.loads(read_bytes(receipt_path).decode('utf-8'))
    conflicts = []
    for op in reversed(receipt['operations']):
        if op.get('restored'):
            continue
        try:
            current = snapshot(op['path'])
        except ValueError:
            conflicts.append(op['path'])
            continue
        if current == op['before']:
            continue
        if current != op['after']:
            conflicts.append(op['path'])
            continue
        before = op['before']
        if before['kind'] == 'absent':
            os.unlink(op['path'])
        elif before['kind'] == 'file':
            data = read_bytes(op['backup'])
            if digest(data) != before['sha256']:
                raise ValueError('Backup checksum mismatch: ' + op['backup'])
            atomic(op['path'], data, before['mode'])
        else:
            raise ValueError('Unexpected rollback state')
        op['restored'] = True
        atomic(receipt_path, json.dumps(receipt, indent=2, sort_keys=True).encode('utf-8'), 384)
    if conflicts:
        raise ValueError('Changed since installation; preserved: ' + ', '.join(conflicts))


def main():
    parser = OptionParser('%prog [--root EDA_ROOT --home USER_HOME] | --rollback RECEIPT')
    parser.add_option('--root', default='/home/disk/eda')
    parser.add_option('--home', default=os.path.expanduser('~'))
    parser.add_option('--rollback')
    options, args = parser.parse_args()
    if args:
        parser.error('Unexpected arguments')
    os.umask(63)
    if options.rollback:
        rollback(os.path.abspath(options.rollback))
        print('Integration rolled back; library and project data retained.')
        return
    library = os.path.join(os.path.realpath(options.root), 'references', 'SKILL-ANALOG')
    if not os.path.isfile(os.path.join(library, 'skills', 'analog-design', 'SKILL.md')):
        raise ValueError('Library must be deployed before integration: ' + library)
    if subprocess.call([sys.executable, os.path.join(library, 'tools', 'analogctl.py'), 'verify']):
        raise ValueError('Library verification failed; integration stopped')
    installer = Installer(options.root, options.home)
    try:
        print('Receipt: ' + installer.integrate())
    except Exception:
        print('Installation incomplete. Review receipt: ' + installer.receipt_dir, file=sys.stderr)
        raise


if __name__ == '__main__':
    try:
        main()
    except (ValueError, IOError, OSError) as error:
        print('ERROR: ' + str(error), file=sys.stderr)
        sys.exit(1)
