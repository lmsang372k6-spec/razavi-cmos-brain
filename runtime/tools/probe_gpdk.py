#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Bounded read-only probe; Python 2.6+ stdlib. Does not run EDA binaries."""
from __future__ import print_function
import hashlib
import json
import os
import re
import sys
sys.dont_write_bytecode = True

ROOT = '/home/disk/eda/apps/cadence/pdks'
TARGETS = [('GPDK045', 'gpdk045_v_5_0', 'gpdk045.scs'),
           ('GPDK090', 'gpdk090_v4.6', 'gpdk090.scs')]


def executable(name):
    for directory in os.environ.get('PATH', '').split(os.pathsep):
        if directory:
            path = os.path.join(directory, name)
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return os.path.realpath(path)
    return None


def model_summary(path):
    digest = hashlib.sha256()
    sections = []
    with open(path, 'rb') as stream:
        for line in stream:
            digest.update(line)
            match = re.match(r'^\s*section\s+([A-Za-z0-9_]+)\b',
                             line.decode('ascii', 'ignore'), re.I)
            if match and match.group(1) not in sections:
                sections.append(match.group(1))
    return {'path': os.path.realpath(path), 'sha256': digest.hexdigest(),
            'top_level_sections': sections,
            'limits': 'No include hierarchy, ratings, CDF or simulator validation.'}


def probe(root=ROOT):
    pdks = []
    for identifier, version, filename in TARGETS:
        base = os.path.join(root, version)
        item = {'id': identifier, 'path': base, 'exists': os.path.isdir(base),
                'models': [], 'errors': []}
        # Only known model subdirectories; never walk projects or virtual disks.
        candidates = [os.path.join(base, 'models', 'spectre', filename),
                      os.path.join(base, identifier.lower(), 'models', 'spectre', filename)]
        seen = set()
        for path in candidates:
            real = os.path.realpath(path)
            if real in seen or not os.path.isfile(path):
                continue
            seen.add(real)
            try:
                item['models'].append(model_summary(path))
            except (IOError, OSError) as error:
                item['errors'].append(str(error))
        pdks.append(item)
    return {'schema': 'skill-analog.gpdk-probe.v1', 'python': sys.version.split()[0],
            'python_executable': sys.executable, 'pdks': pdks,
            'executables_in_path': dict((n, executable(n)) for n in
                ('python', 'python2.7', 'python3', 'virtuoso', 'spectre', 'ocean', 'psf')),
            'runtime_status': 'NOT VERIFIED: no simulator, bridge, or source code executed.'}


if __name__ == '__main__':
    if len(sys.argv) != 1:
        sys.exit('Usage: python probe_gpdk.py (read-only, no arguments)')
    print(json.dumps(probe(), indent=2, sort_keys=True))
