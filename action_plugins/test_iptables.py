# (c) 2017, Hiroaki Nakamura <hnakamur@gmail.com>
#
# test_iptables.py is a third party action plugin for Ansible
#
# test_iptables.py is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# test_iptables.py is distributed in the hope that it will be useful,
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
import re
import time

from ansible import constants as C
from ansible.errors import AnsibleError
from ansible.module_utils._text import to_bytes, to_native, to_text
from ansible.plugins.action import ActionBase
from ansible.utils.boolean import boolean
from ansible.module_utils.six import b


def cook_iptables_save_for_comparision(stdout):
    counter = re.compile(r'\[\d+:\d+\]$')
    lines = []
    # NOTE: first replace CR+LF to LF
    for line in stdout.replace('\r\n', '\n').split('\n'):
        if line.startswith('#'):
            continue
        if line.startswith(':'):
            line = counter.sub('[0:0]', line)
        elif line.startswith('-A'):
            # NOTE: iptables-save in CentOS 6 prints a redundant space at the end of -A lines.
            line = line.rstrip(' ')
        lines.append(line)
    return '\n'.join(lines)

class ActionModule(ActionBase):

    TRANSFERS_FILES = False

    def run(self, tmp=None, task_vars=None):
        ''' handler for template operations '''
        if task_vars is None:
            task_vars = dict()

        result = super(ActionModule, self).run(tmp, task_vars)

        source = self._task.args.get('src', None)
        executable = self._task.args.get('executable', 'iptables-save')

        if source is None:
            result['failed'] = True
            result['msg'] = "src is required"
        else:
            try:
                source = self._find_needle('templates', source)
            except AnsibleError as e:
                result['failed'] = True
                result['msg'] = to_native(e)

        if 'failed' in result:
            return result

        # template the source data locally & get ready to transfer
        b_source = to_bytes(source)
        try:
            with open(b_source, 'r') as f:
                template_data = to_text(f.read())

            try:
                template_uid = pwd.getpwuid(os.stat(b_source).st_uid).pw_name
            except:
                template_uid = os.stat(b_source).st_uid

            temp_vars = task_vars.copy()
            temp_vars['template_host']     = os.uname()[1]
            temp_vars['template_path']     = source
            temp_vars['template_mtime']    = datetime.datetime.fromtimestamp(os.path.getmtime(b_source))
            temp_vars['template_uid']      = template_uid
            temp_vars['template_fullpath'] = os.path.abspath(source)
            temp_vars['template_run_date'] = datetime.datetime.now()

            managed_default = C.DEFAULT_MANAGED_STR
            managed_str = managed_default.format(
                host = temp_vars['template_host'],
                uid  = temp_vars['template_uid'],
                file = to_bytes(temp_vars['template_path'])
            )
            temp_vars['ansible_managed'] = time.strftime(
                managed_str,
                time.localtime(os.path.getmtime(b_source))
            )


            searchpath = []
            # set jinja2 internal search path for includes
            if 'ansible_search_path' in task_vars:
                searchpath = task_vars['ansible_search_path']
                # our search paths aren't actually the proper ones for jinja includes.

            searchpath.extend([self._loader._basedir, os.path.dirname(source)])

            # We want to search into the 'templates' subdir of each search path in
            # addition to our original search paths.
            newsearchpath = []
            for p in searchpath:
                newsearchpath.append(os.path.join(p, 'templates'))
                newsearchpath.append(p)
            searchpath = newsearchpath

            self._templar.environment.loader.searchpath = searchpath

            old_vars = self._templar._available_variables
            self._templar.set_available_variables(temp_vars)
            resultant = self._templar.template(template_data, preserve_trailing_newlines=True, escape_backslashes=False)
            self._templar.set_available_variables(old_vars)
        except Exception as e:
            result['failed'] = True
            result['msg'] = type(e).__name__ + ": " + str(e)
            return result

        cmd_result = self._low_level_execute_command(cmd=executable, sudoable=True)
        if cmd_result['rc'] != 0:
            result['failed'] = True
            result['msg'] = '%s failed with rc=%d, stderr=%s' % (executable, cmd_result['rc'], cmd_result['stderr'])
            return result

        want = resultant
        got = cook_iptables_save_for_comparision(cmd_result['stdout'])
        if got == want:
            result['changed'] = False
        else:
            result['changed'] = True
            result['diff'] = {
                'before_header': 'template result',
                'after_header': 'remote iptables-save cooked result',
                'before': want,
                'after': got
            }

        return result
