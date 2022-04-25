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

from ansible.parsing.dataloader import DataLoader
from ansible.inventory.manager import InventoryManager

import ansible_runner  # noqa


def _playbook_check(play):
    if not os.path.exists(play):
        play = os.path.join(playbook_dir, play)
        if not os.path.exists(play):
            raise RuntimeError('No such playbook: {}'.format(play))
    LOG.debug('Ansible playbook {} found'.format(play))
    return play



class AnsibleRunner:
    """Simple wrapper for ansible-playbook."""

    def __init__(self, workdir: string, moduledir: string = None,
            ssh_user: string = 'root', ssh_key: string = None,
            ansible_cfg: string = None):
        """
        :param inventory: Either proper inventory file, or a coma-separated list.
        :type inventory: String

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
                remote_user=ssh_user,
                private_key_file=ssh_key,
                library=os.path.expanduser(
                    '~/.ansible/plugins/modules:{workdir}/modules:{usr}'
                    '{ansible}/plugins/modules:{ansible}-modules'.format(
                        usr=moduledir, workdir=workdir, ansible='/usr/share/ansible'
                    )
                ),
                lookup_plugins=os.path.expanduser(
                    '~/.ansible/plugins/lookup:{workdir}/lookup:'
                    '{ansible}/plugins/lookup:'.format(
                        workdir=workdir, ansible='/usr/share/ansible'
                    )
                ),
                gathering='smart',
                # etc
                log_path=os.path.join(workdir, 'ansible.log')
            ),
        )
        parser = configparser.ConfigParser()
        parser.read_dict(conf)
        with open(ansible_cfg, 'w') as conffile:
            parser.write(conffile)
        os.environ['ANSIBLE_CONFIG'] = ansible_cfg

    def run(playbook: str, tags: string = None, skip_tags: string = None,
            quiet: bool = False, timeout: int = 30):
        """Run given Ansible playbook.

        :param playbook: Playbook filename.
        :type playbook: String

        :param tags: Run specific tags.
        :type tags: String

        :param skip_tags: Skip specific tags.
        :type skip_tags: String

        :param quiet: Disable all output (Defaults to False)
        :type quiet: Boolean

        :param timeout: Timeout to finish playbook execution (minutes).
        :type timeout: int
        """
        run_opts = {
            'private_data_dir': workdir,
            'inventory': _inventory(inventory),
            'playbook': playbook,
            'verbosity': verbosity,
            'quiet': quiet,
        }

        if skip_tags:
            run_opts['skip_tags'] = skip_tags

        if tags:
            run_opts['tags'] = tags

        runner_config = ansible_runner.runner_config.RunnerConfig(**run_opts)
        runner_config.prepare()
        runner = ansible_runner.Runner(config=runner_config)
        try:
            status, rc = runner.run()
        finally:
            # NOTE(cloudnull): After a playbook executes, ensure the log
            #                  file, if it exists, was created with
            #                  appropriate ownership.
            _log_path = r_opts['envvars']['ANSIBLE_LOG_PATH']
            if os.path.isfile(_log_path):
                os.chown(_log_path, get_uid, -1)
            # Save files we care about
            with open(os.path.join(workdir, 'stdout'), 'w') as f:
                f.write(runner.stdout.read())
            for output in 'status', 'rc':
                val = getattr(runner, output)
                if val:
                    with open(os.path.join(workdir, output), 'w') as f:
                        f.write(str(val))
            if rc != 0:
                err_msg = (
                    'Ansible execution failed. playbook: {},'
                    ' Run Status: {},'
                    ' Return Code: {}'.format(
                        playbook,
                        status,
                        rc
                    )
                )
                if not quiet:
                    LOG.error(err_msg)

                raise RuntimeError(err_msg)
