#   Copyright 2022 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License"); you may
#   not use this file except in compliance with the License. You may obtain
#   a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#   WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#   License for the specific language governing permissions and limitations
#   under the License.
#

import os
import pipes
import shutil
import subprocess
import tempfile


from contextlib import contextmanager
from observabilityclient.utils import strings


@contextmanager
def tempdir(base: str, prefix: str = None, clear: bool = True) -> str:
    path = tempfile.mkdtemp(prefix=prefix, dir=base)
    try:
        yield path
    finally:
        if clear:
            shutil.rmtree(path, ignore_errors=True)


def file_check(path: str, ftype: str = 'file', clear: bool = False) -> str:
    """Check if given path exists and create it in case required."""
    if not os.path.exists(path) or clear:
        if ftype == 'directory':
            if clear:
                shutil.rmtree(path, ignore_errors=True)
            os.makedirs(path, mode=0o700, exist_ok=True)
        elif ftype == 'file':
            with open(path, 'w') as f:
                f.close()
    return path


def execute(cmd, workdir: str = None, can_fail: bool = True,
            mask_list: list = None, use_shell: bool = False):
    """
    Runs given shell command. Returns return code and content of stdout.

    :param workdir: Location of the working directory.
    :type workdir: String

    :param can_fail: If is set to True RuntimeError is raised in case
                     of command returned non-zero return code.
    :type can_fail: Boolean
    """
    mask_list = mask_list or []

    if not isinstance(cmd, str):
        masked = ' '.join((pipes.quote(i) for i in cmd))
    else:
        masked = cmd
    masked = strings.mask_string(masked, mask_list)

    proc = subprocess.Popen(cmd, cwd=workdir, shell=use_shell, close_fds=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    if proc.returncode and can_fail:
        raise RuntimeError('Failed to execute command: %s' % masked)
    return proc.returncode, out, err
