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
module: test_command
short_description: Executes a command on a remote node and check result code, stdout, or stderr.
description:
     - The M(command) module takes the command name followed by a list of space-delimited arguments.
     - The given command will be executed on all selected nodes. It will not be
       processed through the shell, so variables like C($HOME) and operations
       like C("<"), C(">"), C("|"), C(";") and C("&") will not work (use the M(shell)
       module if you need these features).
options:
  cmd:
    description:
      - the command module takes a free form command to run.
        See the examples!
    required: true
    default: null
  chdir:
    description:
      - cd into this directory before running the command
    version_added: "0.6"
    required: false
    default: null
  use_shell:
    default: no
    description:
      - Run a command through shell if set to yes/true.
      - If you want to run a command through the shell (say you are using C(<),
        C(>), C(|), etc), set this to yes/true.
    required: false
  want_rc:
    default: no
    description:
      - The result code of the command execution is compared to this value if specified.
    required: false
  want_stdout:
    default: no
    description:
      - The stdout output of the command execution is compared to this value if specified.
    required: false
  want_stderr:
    default: no
    description:
      - The stderr output of the command execution is compared to this value if specified.
    required: false
note:
    - Exactly one of C(want_rc), C(want_stdout) or C(want_stderr) must be specified.
    - This module executes the command even when ansible is in check mode.
      WARNING: It is users' responsibility to use command line which does NOT modify the environment.
    - The C(changed) value in result is that the result rc, stdout or stderr did match to
      want_rc, want_stdout or want_stderr.
      Note this is different from other standard modules where C(changed) means whether
      the module changed the environment or not.
author: 
    - Hiroaki Nakamura
'''

EXAMPLES = '''
TBD
'''

import datetime
import shlex
import os

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six import b

def main():

    # the command module is the one ansible module that does not take key=value args
    # hence don't copy this one if you are looking to build others!
    module = AnsibleModule(
        argument_spec=dict(
          cmd = dict(type='str', required=True),
          chdir = dict(type='path'),
          use_shell = dict(type='bool', default=False),
          want_rc = dict(type='int'),
          want_stdout = dict(type='str'),
          want_stderr = dict(type='str'),
        ),
        supports_check_mode = True
    )

    chdir = module.params['chdir']
    use_shell = module.params['use_shell']
    cmd = module.params['cmd']
    if cmd.strip() == '':
        module.fail_json(rc=256, msg="no command given")

    want_count = 0
    if module.params['want_rc'] is not None:
        want_count += 1
    if module.params['want_stdout'] is not None:
        want_count += 1
    if module.params['want_stderr'] is not None:
        want_count += 1
    if want_count != 1:
        module.fail_json(rc=256, msg="one of want_rc, want_stdout and want_stderr must be given (not zero or two or more)")

    if chdir:
        chdir = os.path.abspath(chdir)
        os.chdir(chdir)

    if use_shell:
        args = cmd
    else:
        args = shlex.split(cmd)
    startd = datetime.datetime.now()

    rc, out, err = module.run_command(args, use_unsafe_shell=use_shell, encoding=None)

    endd = datetime.datetime.now()
    delta = endd - startd

    if out is None:
        out = b('')
    if err is None:
        err = b('')

    stdout = out.rstrip(b("\r\n"))
    stderr = err.rstrip(b("\r\n"))

    result = {
        'result': {
            'stdout': stdout,
            'stderr': stderr,
            'rc': rc,
        },
        'start': str(startd),
        'end': str(endd),
        'delta': str(delta)
    }

    changed = False
    if module.params['want_rc'] is not None:
        changed = (rc != module.params['want_rc'])
    elif module.params['want_stdout'] is not None:
        want_stdout = module.params['want_stdout']
        changed = (stdout != want_stdout)
        if changed and b("\n") in stdout:
            result['diff'] = {
                'before_header': 'want_stdout',
                'after_header': 'result.stdout',
                'before': want_stdout + b("\n"),
                'after': stdout + b("\n")
            }
    elif module.params['want_stderr'] is not None:
        want_stderr = module.params['want_stderr']
        changed = (stderr != want_stderr)
        if changed and b("\n") in stderr:
            result['diff'] = {
                'before_header': 'want_stderr',
                'after_header': 'result.stderr',
                'before': want_stderr + b("\n"),
                'after': stderr + b("\n")
            }

    result['changed'] = changed

    module.exit_json(**result)

if __name__ == '__main__':
    main()
