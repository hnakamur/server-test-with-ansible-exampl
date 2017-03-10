#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2017, Hiroaki Nakamura <hnakamur@gmail.com>
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
module: test_rpm
short_description: Check the specified rpm is installed or not
description:
     - TBD
options:
  name:
    description:
      - the name of the package.
    required: true
  version:
    description:
      - the version of the package.
    required: false
  state:
    description:
      - the expected installation state.
    required: false
    choices: [ "present", "absent" ]
    default: present
author: 
    - Hiroaki Nakamura
'''

EXAMPLES = '''
TBD
'''

from ansible.module_utils.basic import AnsibleModule

def main():

    module = AnsibleModule(
        argument_spec=dict(
          name = dict(type='str', required=True),
          version = dict(type='str', required=False),
          state=dict(default='present', choices=['absent','present']),
        ),
        supports_check_mode = True
    )

    name = module.params['name']
    version = module.params['version']
    state = module.params['state']

    rpmbin = module.get_bin_path('rpm', required=True)

    # rpm localizes messages and we're screen scraping so make sure we use
    # the C locale
    lang_env = dict(LANG='C', LC_ALL='C', LC_MESSAGES='C')
    cmd = '%s -q %s' % (rpmbin, name)
    rc, out, err = module.run_command(cmd, environ_update=lang_env)
    out = out.rstrip('\n')

    got_state = 'present'
    got_version = None
    if rc != 0:
        if 'is not installed' in out:
            got_state = 'absent'
        else:
            module.fail_json(msg='Error from rpm: %s: %s' % (cmd, err))
    else:
        if not out.startswith('%s-' % name):
            module.fail_json(msg='Unexpected rpm output=%s: command=%s: output should be starts with %s-' % (out, cmd, err))
        got_version = out[len('%s-' % name):]

    result = {
        'module': 'test_rpm',
        'name': name,
        'state': {
            'got': got_state,
            'want': state,
        },
        '_ansible_verbose_always': True
    }

    if got_version:
        result['version'] = {
            'got': got_version
        }

    changed = (got_state != state)
    if state == 'present' and version is not None:
        if 'version' not in result:
            result['version'] = {}
        result['version']['want'] = version
        if got_version != version:
            changed = True

    result['changed'] = changed
    module.exit_json(**result)

if __name__ == '__main__':
    main()
