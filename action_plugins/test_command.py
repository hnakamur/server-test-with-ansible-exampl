# (c) 2015, Michael DeHaan <michael.dehaan@gmail.com>
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
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import datetime
import os
import pwd
import time

from ansible import constants as C
from ansible.compat.six import string_types
from ansible.errors import AnsibleError
from ansible.module_utils._text import to_bytes, to_native, to_text
from ansible.plugins.action import ActionBase
from ansible.utils.hashing import checksum_s
from ansible.utils.boolean import boolean


class ActionModule(ActionBase):

    TRANSFERS_FILES = True

    def run(self, tmp=None, task_vars=None):
        ''' handler for template operations '''
        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)
        if 'failed' not in result:
            result['failed'] = False

        cmd = self._task.args.get('cmd', None)
        want_stdout = self._task.args.get('want_stdout', None)
        if 'want_stdout' in self._task.args:
            result['want_stdout'] = want_stdout

        cmd_result = self._low_level_execute_command(cmd=cmd)
        result['cmd'] = cmd
        result['rc'] = cmd_result['rc']
        result['stdout'] = cmd_result['stdout']
        result['stderr'] = cmd_result['stderr']

        got_stdout = cmd_result["stdout"].rstrip("\n")
        if want_stdout is not None and got_stdout != want_stdout:
            diff = {
                "before": want_stdout + "\n",
                "after": got_stdout + "\n",
                "before_header": "expected result",
                "after_header": "actual result",
            }
            result['diff'] = diff
            result['changed'] = True

        return result
