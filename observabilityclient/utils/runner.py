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

import ansible_runner
import configparser
import os
import shutil

from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from ansible.vars.manager import VariableManager

from observabilityclient.utils import shell


class AnsibleRunnerException(Exception):
    """Base exception class for runner exceptions"""


class AnsibleRunnerFailed(AnsibleRunnerException):
    """Raised when ansible run failed"""

    def __init__(self, status, rc, stderr):
        super(AnsibleRunnerFailed).__init__()
        self.status = status
        self.rc = rc
        self.stderr = stderr

    def __str__(self):
        return ('Ansible run failed with status {}'
                ' (return code {}):\n{}').format(self.status, self.rc,
                                                 self.stderr)


def parse_inventory_hosts(inventory):
    """Returns list of dictionaries. Each dictionary contains info about
    single node from inventory.
    """
    dl = DataLoader()
    if isinstance(inventory, str):
        inventory = [inventory]
    im = InventoryManager(loader=dl, sources=inventory)
    vm = VariableManager(loader=dl, inventory=im)

    out = []
    for host in im.get_hosts():
        data = vm.get_vars(host=host)
        out.append(
            dict(host=data.get('inventory_hostname', str(host)),
                 ip=data.get('ctlplane_ip', data.get('ansible_host')),
                 hostname=data.get('canonical_hostname'))
        )
    return out


class AnsibleRunner:
    """Simple wrapper for ansible-playbook."""

    def __init__(self, workdir: str, moduledir: str = None,
                 ssh_user: str = 'root', ssh_key: str = None,
                 ansible_cfg: str = None):
        """
        :param workdir: Location of the working directory.
        :type workdir: String

        :param ssh_user: User for the ssh connection.
        :type ssh_user: String

        :param ssh_key: Private key to use for the ssh connection.
        :type ssh_key: String

        :param moduledir: Location of the ansible module and library.
        :type moduledir: String

        :param ansible_cfg: Path to an ansible configuration file.
        :type ansible_cfg: String
        """
        self.workdir = shell.file_check(workdir, ftype='directory')

        if moduledir is None:
            moduledir = ''
        ansible_cfg = ansible_cfg or os.path.join(workdir, 'ansible.cfg')
        if not os.path.exists(ansible_cfg):
            conf = dict(
                ssh_connection=dict(
                    ssh_args=(
                        '-o UserKnownHostsFile={} '
                        '-o StrictHostKeyChecking=no '
                        '-o ControlMaster=auto '
                        '-o ControlPersist=30m '
                        '-o ServerAliveInterval=64 '
                        '-o ServerAliveCountMax=1024 '
                        '-o Compression=no '
                        '-o TCPKeepAlive=yes '
                        '-o VerifyHostKeyDNS=no '
                        '-o ForwardX11=no '
                        '-o ForwardAgent=yes '
                        '-o PreferredAuthentications=publickey '
                        '-T'
                    ).format(os.devnull),
                    retries=3,
                    timeout=30,
                    scp_if_ssh=True,
                    pipelining=True
                ),
                defaults=dict(
                    deprecation_warnings=False,
                    remote_user=ssh_user,
                    private_key_file=ssh_key,
                    library=os.path.expanduser(
                        '~/.ansible/plugins/modules:{workdir}/modules:'
                        '{userdir}:{ansible}/plugins/modules:'
                        '{ansible}-modules'.format(
                            userdir=moduledir, workdir=workdir,
                            ansible='/usr/share/ansible'
                        )
                    ),
                    lookup_plugins=os.path.expanduser(
                        '~/.ansible/plugins/lookup:{workdir}/lookup:'
                        '{ansible}/plugins/lookup:'.format(
                            workdir=workdir, ansible='/usr/share/ansible'
                        )
                    ),
                    gathering='smart',
                    log_path=shell.file_check(
                        os.path.join(workdir, 'ansible.log'),
                        clear=True
                    )
                ),
            )
            parser = configparser.ConfigParser()
            parser.read_dict(conf)
            with open(ansible_cfg, 'w') as conffile:
                parser.write(conffile)
        os.environ['ANSIBLE_CONFIG'] = ansible_cfg

    def run(self, playbook, tags: str = None, skip_tags: str = None,
            timeout: int = 30, quiet: bool = False, debug: bool = False):
        """Run given Ansible playbook.

        :param playbook: Playbook filename.
        :type playbook: String

        :param tags: Run specific tags.
        :type tags: String

        :param skip_tags: Skip specific tags.
        :type skip_tags: String

        :param timeout: Timeout to finish playbook execution (minutes).
        :type timeout: int

        :param quiet: Disable all output (Defaults to False)
        :type quiet: Boolean

        :param debug: Enable debug output (Defaults to False)
        :type quiet: Boolean
        """
        kwargs = {
            'private_data_dir': self.workdir,
            'verbosity': 3 if debug else 0,
        }
        locs = locals()
        for arg in ['playbook', 'tags', 'skip_tags', 'quiet']:
            if locs[arg] is not None:
                kwargs[arg] = locs[arg]
        run_conf = ansible_runner.runner_config.RunnerConfig(**kwargs)
        run_conf.prepare()
        run = ansible_runner.Runner(config=run_conf)
        try:
            status, rc = run.run()
        finally:
            if status in ['failed', 'timeout', 'canceled'] or rc != 0:
                err = getattr(run, 'stderr', getattr(run, 'stdout', None))
                if err:
                    error = err.read()
                else:
                    error = "Ansible failed with status %s" % status
                raise AnsibleRunnerFailed(status, rc, error)

    def destroy(self, clear: bool = False):
        """Cleans environment after Ansible run.

        :param clear: Clear also workdir
        :type clear: Boolean
        """
        del os.environ['ANSIBLE_CONFIG']
        if clear:
            shutil.rmtree(self.workdir, ignore_errors=True)
