#!/usr/bin/env python
"""Ask native app-server for skill discovery; no model turn or API request."""
from __future__ import print_function
import os
import sys
import json
import time
import select
import subprocess

sys.dont_write_bytecode = True


def main():
    library = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    executable = os.path.expanduser('~/.local/bin/codex')
    cwd = os.path.abspath(sys.argv[1] if len(sys.argv) == 2 else os.getcwd())
    if len(sys.argv) > 2 or not os.path.isdir(cwd):
        raise ValueError('Usage: python integration/probe-codex.py [EXISTING_DIRECTORY]')
    devnull = open(os.devnull, 'wb')
    process = subprocess.Popen([executable, 'app-server'], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=devnull, bufsize=0)

    def send(message):
        process.stdin.write((json.dumps(message) + '\n').encode('utf-8'))
        process.stdin.flush()

    def response(identifier):
        deadline = time.time() + 25
        while time.time() < deadline:
            ready, unused, unused2 = select.select([process.stdout], [], [], max(0, deadline-time.time()))
            if not ready:
                break
            line = process.stdout.readline()
            if not line:
                raise ValueError('Codex app-server exited before discovery response')
            message = json.loads(line.decode('utf-8'))
            if message.get('id') == identifier:
                if 'error' in message:
                    raise ValueError('Codex protocol error: ' + json.dumps(message['error']))
                return message['result']
        raise ValueError('Codex discovery request timed out')

    try:
        send({'id': 1, 'method': 'initialize', 'params': {
            'clientInfo': {'name': 'skill-analog-verifier', 'version': '1.0'},
            'capabilities': {'experimentalApi': True}}})
        response(1)
        send({'method': 'initialized'})
        send({'id': 2, 'method': 'skills/list', 'params': {'cwds': [cwd], 'forceReload': True}})
        result = response(2)
        entries = result.get('data', [])
        matches = []
        errors = []
        for entry in entries:
            errors.extend(entry.get('errors', []))
            for skill in entry.get('skills', []):
                if skill.get('name') == 'analog-design':
                    matches.append(dict((key, skill.get(key)) for key in ('name', 'path', 'scope', 'enabled')))
        expected = os.path.join(library, 'skills', 'analog-design', 'SKILL.md')
        valid = [s for s in matches if s.get('enabled') is True and
                 os.path.realpath(s.get('path') or '') == expected]
        output = {'command': 'probe-codex', 'cwd': cwd, 'ok': len(valid) == 1 and len(matches) == 1,
                  'analog_skill_entries': matches, 'skill_errors': errors,
                  'model_turn_executed': False,
                  'limit': 'Native discovery only; does not prove model compliance or EDA compatibility.'}
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0 if output['ok'] else 1
    finally:
        try:
            process.stdin.close()
        except IOError:
            pass
        if process.poll() is None:
            process.terminate()
        process.wait()
        devnull.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, IOError, OSError) as error:
        print(json.dumps({'command': 'probe-codex', 'ok': False, 'error': str(error),
                          'model_turn_executed': False}))
        sys.exit(2)
