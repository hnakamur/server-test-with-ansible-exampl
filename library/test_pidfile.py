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
module: test_pidfile
short_description: Check the pid file and process exists or not.
description:
     - TBD
options:
  name:
    description:
      - the path of the pid file.
    required: true
  state:
    description:
      - the expected state of the pid file and the process.
    required: false
    choices: [ "present", "absent" ]
    default: present
  pattern:
    description:
      - the regular expression to match the process.
        if the process name (the part between ( and ) of /proc/*/stat) or
        the command line (/proc/*/cmdline) matches to this pattern,
        it means the process exists.
    required: True
  match_full:
    description:
      - match the pattern to the whole command line if set to yes.
        match the pattern to the part between ( and ) of /proc/*/stat if set to no.
    required: false
    choices: [ "yes", "no" ]
    default: no
author: 
    - Hiroaki Nakamura
'''

EXAMPLES = '''
TBD
'''

import re

from ansible.module_utils.basic import AnsibleModule

def main():

    module = AnsibleModule(
        argument_spec=dict(
          name = dict(type='str', required=True),
          state=dict(default='present', choices=['absent','present']),
          pattern = dict(type='str', required=True),
          match_full=dict(type='bool', default=False),
        ),
        supports_check_mode = True
    )

    name = module.params['name']
    state = module.params['state']
    pattern = module.params['pattern']
    match_full = module.params['match_full']

    ps_bin = module.get_bin_path('ps', required=True)

    result = {
        'name': name,
        '_ansible_verbose_always': True
    }

    got_state = 'absent'

    pid = ''
    try:
        pid = open(name).read().strip()
        result['pid'] = pid
    except IOError as e:
        if not e.args[1].startswith('No such file or directory'):
            module.fail_json(msg='Error cannot read pidfile: %s' % str(e))

    if len(pid) == 0:
        result['state'] = got_state
        result['changed'] = (got_state != state)
        module.exit_json(**result)
        return

    ps_cmd = '%s uww -p %s' % (ps_bin, pid)
    ps_rc, ps_out, ps_err = module.run_command(ps_cmd, encoding=None)
    result['ps'] = {
        'cmd': ps_cmd,
        'rc': ps_rc,
        'stderr': ps_err,
    }
    result['stdout'] = ps_out

    match_target = None
    if match_full:
        try:
            cmdline_path = '/proc/%s/cmdline' % pid
            cmdline = open(cmdline_path).read()
            result['cmdline'] = cmdline
            match_target = cmdline
        except IOError as e:
            if not e.args[1].startswith('No such file or directory'):
                module.fail_json(msg='Error cannot read cmdline file: %s' % str(e))
    else:
        try:
            stat_path = '/proc/%s/stat' % pid
            stat = open(stat_path).read()
            result['stat'] = stat
            m = re.search(r'\(([^)]+)\)', stat)
            if m:
                match_target = m.group(1)
        except IOError as e:
            if not e.args[1].startswith('No such file or directory'):
                module.fail_json(msg='Error cannot read stat file: %s' % str(e))

    if match_target is not None:
        got_state = re.search(pattern, match_target) is None and 'absent' or 'present'
    result['state'] = got_state
    result['changed'] = (got_state != state)

    module.exit_json(**result)

if __name__ == '__main__':
    main()
