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

import argparse
import os
import shutil
import tempfile

from osc_lib.command import command
from osc_lib.i18n import _

from observabilityclient.utils import runner
from observabilityclient.utils import shell


OBSLIBDIR = shell.file_check('/usr/share/openstack-observability', 'directory')
OBSWRKDIR = shell.file_check('/var/lib/openstack-observability', 'directory')
OBSTMPDIR = shell.file_check(os.path.join(OBSWRKDIR, 'tmp'), 'directory')


class ObservabilityBaseCommand(command.Command):
    """Base class for observability commands."""

    def get_parser(self, prog_name):
        parser = argparse.ArgumentParser(
            description=self.get_description(),
            prog=prog_name,
            add_help=False
        )
        parser.add_argument(
            '-w',
            '--workdir',
            default=OBSWRKDIR,
            help=_("Working directory for observability commands.")
        )
        parser.add_argument(
            '-m',
            '--moduledir',
            default=None,
            help=_("Directory with additional Ansible modules.")
        )
        parser.add_argument(
            '-u',
            '--ssh_user',
            default='heat-admin',
            help=_("Username to be used for SSH connection.")
        )
        parser.add_argument(
            '-k',
            '--ssh_key',
            default='/home/stack/.ssh/id_rsa',
            help=_("SSH private key to be used for SSH connection.")
        )
        parser.add_argument(
            '-c',
            '--ansible_cfg',
            default=os.path.join(OBSWRKDIR, 'ansible.cfg'),
            help=_("Path to Ansible configuration.")
        )
        return parser

    def _run_playbook(self, playbook, inventory, parsed_args):
        """Run Ansible playbook"""
        rnr = runner.AnsibleRunner(parsed_args.workdir,
                                   moduledir=parsed_args.moduledir,
                                   ssh_user=parsed_args.ssh_user,
                                   ssh_key=parsed_args.ssh_key,
                                   ansible_cfg=parsed_args.ansible_cfg)
        rnr.run(playbook, inventory)
        rnr.destroy()

    def _execute(self, command):
        """Execute local command"""
        tmpdir = tempfile.mkdtemp(prefix=None, dir=OBSTMPDIR)
        shell.execute(command, workdir=tmpdir, can_fail=False, use_shell=True)
        shutil.rmtree(tmpdir, ignore_errors=True)
