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
      - the command module takes a free form command to run.
        See the examples!
    required: true
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
          state=dict(default='present', choices=['absent','present']),
        ),
        supports_check_mode = True
    )

    name = module.params['name']
    state = module.params['state']

    rpmbin = module.get_bin_path('rpm', required=True)

    # rpm localizes messages and we're screen scraping so make sure we use
    # the C locale
    lang_env = dict(LANG='C', LC_ALL='C', LC_MESSAGES='C')
    cmd = '%s -q %s' % (rpmbin, name)
    rc, out, err = module.run_command(cmd, environ_update=lang_env)
    if rc != 0 and 'is not installed' not in out:
    	module.fail_json(msg='Error from rpm: %s: %s' % (cmd, err))

    got_state = 'present'
    if 'is not installed' in out:
    	got_state = 'absent'

    result = {
        'name': name,
        'state': got_state,
        'changed': got_state != state,
        'stdout': out.rstrip('\n'),
        '_ansible_verbose_always': True
    }

    module.exit_json(**result)

if __name__ == '__main__':
    main()
