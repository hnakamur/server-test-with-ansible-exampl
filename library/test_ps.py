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
module: test_ps
short_description: Check the specified process exists or not.
description:
     - TBD
options:
  name:
    description:
      - the pattern to search processes.
        See the examples!
    required: true
  state:
    description:
      - the expected installation state.
    required: false
    choices: [ "present", "absent" ]
    default: present
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

from ansible.module_utils.basic import AnsibleModule

def main():

    module = AnsibleModule(
        argument_spec=dict(
          name = dict(type='str', required=True),
          state=dict(default='present', choices=['absent','present']),
          match_full=dict(type='bool', default=False),
        ),
        supports_check_mode = True
    )

    name = module.params['name']
    state = module.params['state']
    match_full = module.params['match_full']

    ps_bin = module.get_bin_path('ps', required=True)
    pgrep_bin = module.get_bin_path('pgrep', required=True)
    pgrep_opt = match_full and " -f" or ""

    result = {
        'name': name,
        '_ansible_verbose_always': True
    }

    if name == '*':
        ps_cmd = '%s auxww' % ps_bin
    else:
        pgrep_cmd = '%s%s %s' % (pgrep_bin, pgrep_opt, name)
        pgrep_rc, pgrep_out, pgrep_err = module.run_command(pgrep_cmd, encoding=None)
        if pgrep_rc not in [0, 1]:
            module.fail_json(msg='Error from pgrep: cmd=%s, rc=%d, err=%s' % (pgrep_cmd, pgrep_rc, pgrep_err))
        result['pgrep'] = {
            'cmd': pgrep_cmd,
            'rc': pgrep_rc,
            'stdout': pgrep_out,
            'stderr': pgrep_err,
        }

        if len(pgrep_out.strip()) > 0:
            pids = ' '.join(pgrep_out.rstrip('\n').split('\n'))
            ps_cmd = '%s uww -p %s' % (ps_bin, pids)
        else:
            ps_cmd = ''

    if ps_cmd != '':
        ps_rc, ps_out, ps_err = module.run_command(ps_cmd, encoding=None)
        if ps_rc != 0:
            module.fail_json(msg='Error from ps: cmd=%s, rc=%d, err=%s' % (ps_cmd, ps_rc, ps_err))
        result['ps'] = {
            'cmd': ps_cmd,
            'rc': ps_rc,
            'stderr': ps_err,
        }
        result['stdout'] = ps_out
    else:
        ps_out = ''

    got_state = len(ps_out.strip()) > 0 and 'present' or 'absent'
    result['state'] = got_state
    result['changed'] = (got_state != state)
    module.exit_json(**result)

if __name__ == '__main__':
    main()
