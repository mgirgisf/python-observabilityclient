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


def _curl(host: dict, port: int, timeout: int = 1) -> str:
    """Returns scraping endpoint URL if it is reachable
    otherwise returns None."""
    url = f'http://{host["ip"]}:{port}/metrics'
    try:
        r = requests.get(url, timeout=1)
        if r.status_code != 200:
            url = None
        r.close()
    except requests.exceptions.ConnectionError:
        url = None
    return url


class Discover(base.ObservabilityBaseCommand):
    """Generate Ansible inventory file and scrapable enpoints list file."""

    def get_parser(self, prog_name):
        parser = super().get_parser(prog_name)
        parser.add_argument(
            '--scrape',
            action='append',
            default=['collectd/9666'],
            help=_("Service/Port of scrape endpoint to check on nodes")
        )
        return parser

    def take_action(self, parsed_args):
        # discover undercloud and overcloud nodes
        rc, out, err = self._execute(
            'tripleo-ansible-inventory '
            '--static-yaml-inventory {}'.format(INVENTORY),
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
                if parsed_args.dev:
                    name = host["hostname"] if host["hostname"] else host["ip"]
                    print(f'Trying to fetch {service} metrics on host '
                          f'{name} at port {port}', end='')
                node = _curl(host, port, timeout=1)
                if node:
                    endpoints.setdefault(service.strip(), []).append(node)
                if parsed_args.dev:
                    print(' [success]' if node else ' [failure]')
        data = yaml.safe_dump(endpoints, default_flow_style=False)
        with open(ENDPOINTS, 'w') as f:
            f.write(data)
        print("Discovered following scraping endpoints:\n%s" % data)


class Setup(base.ObservabilityBaseCommand):
    """Install and configure given Observability component(s)"""

    auth_required = False

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
