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
import sys

from osc_lib.i18n import _

from observabilityclient.v1 import base


INVENTORY = os.path.join(base.OBSWRKDIR, 'openstack-inventory.yaml')
STACKRC = os.path.join(base.OBSWRKDIR, 'stackrc')
STACKRCKEYS = ('OS_AUTH_TYPE', 'OS_PASSWORD', 'OS_AUTH_URL', 'OS_USERNAME',
               'OS_PROJECT_NAME', 'OS_NO_CACHE', 'COMPUTE_API_VERSION',
               'OS_USER_DOMAIN_NAME', 'OS_CLOUDNAME', 'OS_PROJECT_DOMAIN_NAME',
               'OS_IDENTITY_API_VERSION', 'NOVA_VERSION')


class Discover(base.ObservabilityBaseCommand):
    """Install and configure given Observability component(s)"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '-r',
            '--rcfile',
            default=None,
            help=_("Path to rc file used for Keystone authentication.")
        )
        return parser

    def take_action(self, parsed_args):
        # make sure we have rc file provided or ready
        if not parsed_args.rcfile:
            env = os.environ.keys()
            have = True
            for key in STACKRCKEYS:
                if key not in env:
                    have = False
                    break
            if not os.path.exists(STACKRC):
                if have:
                    with open(STACKRC, 'w') as f:
                        for key in STACKRCKEYS:
                            f.write('{}={}\n'.format(key, os.environ[key]))
                    os.chmod(STACKRC, 0o600)
                else:
                    print(_('Keystone auth is required. Either provide rc file'
                            'or source one before running the command.'))
                    sys.exit(1)

        # discover undercloud and overcloud nodes
        stackrc = parsed_args.rcfile if parsed_args.rcfile else STACKRC
        self._execute('. {} && tripleo-ansible-inventory'
                      ' --static-yaml-inventory {}'.format(stackrc, INVENTORY))
        # TODO: discover which nodes have observability ports open and provide
        #   /metrics url node for scraping for Prometheus agent configuration


class Setup(base.ObservabilityBaseCommand):
    """Install and configure given Observability component(s)"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            'components',
            nargs='+',
            choices=[
                'prometheus_agent',
                # TODO: in future will contain option for all stack components
            ]
        )
        return parser

    def take_action(self, parsed_args):
        for compnt in parsed_args.components:
            playfile = os.path.join(
                base.OBSLIBDIR,
                'openstack-observability-ansible',
                'playbooks',
                '%s.yaml' % compnt
            )
            self._run_playbook(playfile, INVENTORY, parsed_args=parsed_args)
