#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2012, Michael DeHaan <michael.dehaan@gmail.com>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: test_systemd
author:
    - "Hiroaki Nakamura"
version_added: "0.1"
short_description:  Examine systemd services.
description:
    - Examine service status on remote hosts and make sure it is in the expected status.
options:
    name:
        required: true
        description:
        - Name of the service.
    state:
        required: false
        choices: [ started, stopped ]
        description:
          - If the C(state) is specified, it will be checked that the service
            is in the specified state.
    enabled:
        required: false
        choices: [ "yes", "no" ]
        description:
        - If the C(enabled) is specified, it will be checked that the service
          is enabled at the OS startup.
    defined:
        required: false
        choices: [ "yes", "no" ]
        description:
        - It will be checked that the service is defined or not.
    user:
        required: false
        default: no
        choices: [ "yes", "no" ]
        description:
            - run systemctl talking to the service manager of the calling user, rather than the service manager
              of the system.
'''

EXAMPLES = '''
# Example action to check service httpd is started
- test_systemd: name=httpd state=started

# Example action to check service httpd is stopped and service is not enabled
- test_systemd: name=httpd state=stopped enabled=False

# Example action to check service httpd is enabled, and not check the running state
- test_systemd: name=httpd enabled=yes

# Example action to check service httpd is not defined (not installed)
- test_systemd: name=httpd defined=no

'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_native
import pipes

def service_exists(module, systemctl, quoted_unit, result):
    found = False
    cmd = "%s show --property LoadState %s" % (systemctl, quoted_unit)
    (rc, out, err) = module.run_command(cmd)
    result['defined']['cmd'] = cmd
    result['defined']['rc'] = rc
    result['defined']['stdout'] = out
    result['defined']['err'] = err
    if rc == 0 and out:
        for line in to_native(out).split('\n'): # systemd can have multiline values delimited with {}
            if '=' in line:
                k, v = line.split('=', 1)
                if k == 'LoadState' and v != 'not-found':
                    found = True
    return found

def service_state(module, systemctl, quoted_unit, result):
    state = "stopped"
    cmd = "%s is-active %s" % (systemctl, quoted_unit)
    (rc, out, err) = module.run_command(cmd)
    result['state']['cmd'] = cmd
    result['state']['rc'] = rc
    result['state']['stdout'] = out
    result['state']['err'] = err
    if rc == 0 and out:
        if to_native(out).rstrip('\n') == "active":
            state = "started"
    return state

def service_enabled(module, systemctl, quoted_unit, result):
    state = False
    cmd = "%s is-enabled %s" % (systemctl, quoted_unit)
    (rc, out, err) = module.run_command(cmd)
    result['enabled']['cmd'] = cmd
    result['enabled']['rc'] = rc
    result['enabled']['stdout'] = out
    result['enabled']['err'] = err
    if rc == 0 and out:
        if to_native(out).rstrip('\n') == "enabled":
            state = True
    return state

# ===========================================
# Main control flow

def main():
    module = AnsibleModule(
        argument_spec = dict(
            name = dict(required=True),
            state = dict(choices=['started', 'stopped']),
            enabled = dict(type='bool'),
            defined = dict(type='bool'),
            user= dict(type='bool', default=False),
        ),
        supports_check_mode=True,
        required_one_of=[['state', 'enabled', 'defined']],
    )

    systemctl = module.get_bin_path('systemctl')
    if module.params['user']:
        systemctl = systemctl + " --user"

    unit = module.params['name']
    quoted_unit = pipes.quote(unit)

    result = {
        'name':  unit,
        'defined': {},
        'state': {},
        'enabled': {},
        'module': 'test_systemd',
        '_ansible_verbose_always': True
    }

    changed = False
    result['defined']['got'] = found = service_exists(module, systemctl, quoted_unit, result)
    if module.params['defined'] is not None:
        result['defined']['want'] = module.params['defined']
        result['defined']['changed'] = (result['defined']['got'] != result['defined']['want'])
        changed = changed or result['defined']['changed']

    if module.params['state'] is not None:
        result['state']['want'] = module.params['state']
        if found:
            result['state']['got'] = service_state(module, systemctl, quoted_unit, result)
            result['state']['changed'] = (result['state']['got'] != result['state']['want'])
            changed = changed or result['state']['changed']

    if module.params['enabled'] is not None:
        result['enabled']['want'] = module.params['enabled']
        if found:
            result['enabled']['got'] = service_enabled(module, systemctl, quoted_unit, result)
            result['enabled']['changed'] = (result['enabled']['got'] != result['enabled']['want'])
            changed = changed or result['enabled']['changed']

    result['changed'] = changed
    module.exit_json(**result)

from ansible.module_utils.basic import *

main()
