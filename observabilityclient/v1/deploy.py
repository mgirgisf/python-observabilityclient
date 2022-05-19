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
import requests
import sys
import yaml

from osc_lib.i18n import _

from observabilityclient.v1 import base
from observabilityclient.utils import runner


INVENTORY = os.path.join(base.OBSWRKDIR, 'openstack-inventory.yaml')
ENDPOINTS = os.path.join(base.OBSWRKDIR, 'scrape-endpoints.yaml')
STACKRC = os.path.join(base.OBSWRKDIR, 'stackrc')
STACKRCKEYS = ('OS_AUTH_TYPE', 'OS_PASSWORD', 'OS_AUTH_URL', 'OS_USERNAME',
               'OS_PROJECT_NAME', 'OS_NO_CACHE', 'COMPUTE_API_VERSION',
               'OS_USER_DOMAIN_NAME', 'OS_CLOUDNAME', 'OS_PROJECT_DOMAIN_NAME',
               'OS_IDENTITY_API_VERSION', 'NOVA_VERSION')


def _curl(host: dict, port: int, timeout: int = 1) -> str:
    """Returns scraping endpoint URL if it is reachable
    otherwise returns None."""
    url = f'http://{host["ip"]}:{port}/metrics'
    try:
        r = requests.get(url, timeout=1)
    except requests.exceptions.ConnectionError:
        url = None
    if r.status_code != 200:
        url = None
    r.close()
    return url


class Discover(base.ObservabilityBaseCommand):
    """Install and configure given Observability component(s)"""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
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
        rc, out, err = self._execute(
            '. {} && tripleo-ansible-inventory '
            '--static-yaml-inventory {}'.format(stackrc, INVENTORY),
            parsed_args
        )
        if rc:
            print('Failed to generate Ansible inventory:\n%s\n%s' % (err, out))
            sys.exit(1)

        # discover scrape endpoints
        endpoints = dict()
        hosts = runner.parse_inventory_hosts(INVENTORY)
        for scrape in parsed_args.scrape:
            service, port = scrape.split('/')
            for host in hosts:
                node = _curl(host, port, timeout=1)
                if node:
                    endpoints.setdefault(service.strip(), []).append(node)
                elif parsed_args.dev:
                    print(f'Failed to fetch {service} metrics on {host["ip"]}')
        data = yaml.safe_dump(endpoints, default_flow_style=False)
        with open(ENDPOINTS, 'w') as f:
            data = yaml.dump(endpoints, f)
        print("Discovered following scraping endpoints:\n%s" % data)


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
            playbook = '%s.yml' % compnt
            try:
                self._run_playbook(playbook, INVENTORY,
                                   parsed_args=parsed_args)
            except OSError as ex:
                print('Failed to load playbook file: %s' % ex)
                sys.exit(1)
            except yaml.YAMLError as ex:
                print('Failed to parse playbook configuration: %s' % ex)
                sys.exit(1)
            except runner.AnsibleRunnerFailed as ex:
                print('Ansible run %s (rc %d)' % (ex.status, ex.rc))
                if parsed_args.dev:
                    print(ex.stderr)
