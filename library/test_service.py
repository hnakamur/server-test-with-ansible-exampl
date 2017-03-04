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
module: test_service
author:
    - "Hiroaki Nakamura"
version_added: "0.1"
short_description:  Examine services.
description:
    - Examine service status on remote hosts and make sure it is in the expected status.
      Currently only CentOS 6 and 7 are supported
      (Actually CentOS 7 is supported in the test_systemd module).
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
'''

EXAMPLES = '''
# Example action to check service httpd is started
- test_service: name=httpd state=started

# Example action to check service httpd is stopped
- test_service: name=httpd state=stopped

# Example action to check service httpd is enabled, and not check the running state
- test_service: name=httpd enabled=yes

# Example action to check service httpd is not defined (not installed)
- test_service: name=httpd defined=no

'''

import platform
import pipes
#import os
#import re
#import tempfile
#import shlex
#import select
#import time
#import string
#import glob

# The distutils module is not shipped with SUNWPython on Solaris.
# It's in the SUNWPython-devel package which also contains development files
# that don't belong on production boxes.  Since our Solaris code doesn't
# depend on LooseVersion, do not import it on Solaris.
if platform.system() != 'SunOS':
    from distutils.version import LooseVersion

class TestService(object):
    """
    This is the generic Service examination class that is subclassed
    based on platform.

    A subclass should override the following action methods:-
      - get_service_defined
      - get_service_status
      - get_service_enabled

    All subclasses MUST define platform and distribution (which may be None).
    """

    platform = 'Generic'
    distribution = None

    def __new__(cls, *args, **kwargs):
        return load_platform_subclass(TestService, args, kwargs)

    def __init__(self, module):
        self.module         = module
        self.name           = module.params['name']
        self.quoted_name    = pipes.quote(self.name)
        self.state          = module.params['state']
        self.enable         = module.params['enabled']
        self.defined        = module.params['defined']
        self.changed        = False
        self.running        = None
        self.crashed        = None
        self.svc_cmd        = None
        self.svc_initscript = None
        self.svc_initscript_exists = False
        self.svc_initctl    = None
        self.enable_cmd     = None
        self.rcconf_file    = None
        self.rcconf_key     = None
        self.rcconf_value   = None
        self.svc_change     = False

    # ===========================================
    # Platform specific methods (must be replaced by subclass).

    def get_service_defined(self):
        self.module.fail_json(msg="get_service_defined not implemented on target platform")

    def get_service_status(self):
        self.module.fail_json(msg="get_service_status not implemented on target platform")

    def get_service_enabled(self):
        self.module.fail_json(msg="get_service_enabled not implemented on target platform")

    # ===========================================
    # Generic methods that should be used on all platforms.

    def execute_command(self, cmd):
        return self.module.run_command(cmd)

# ===========================================
# Subclass: Linux

class LinuxTestService(TestService):
    """
    This is the Linux Service examination class - it is currently supporting
    a mixture of binaries and init scripts for checking services are defined, started at
    boot, as well as for checking the current state.
    """

    platform = 'Linux'
    distribution = None

    def __init__(self, module):
        super(LinuxTestService, self).__init__(module)
        self.svc_cmd = None
        self.svc_initscript = None

    def get_service_tools(self):
        paths = [ '/sbin', '/usr/sbin', '/bin', '/usr/bin' ]
        binaries = [ 'service', 'chkconfig', 'update-rc.d', 'rc-service', 'rc-update', 'initctl', 'start', 'stop', 'restart', 'insserv' ]
        initpaths = [ '/etc/init.d' ]
        location = dict()

        for binary in binaries:
            location[binary] = self.module.get_bin_path(binary, opt_dirs=paths)

        for initdir in initpaths:
            self.svc_initscript = "%s/%s" % (initdir, self.name)
            if os.path.isfile(self.svc_initscript):
                self.svc_initscript_exists = True
                break

        # Locate a tool to enable/disable a service
        if location.get('initctl', False) and os.path.exists("/etc/init/%s.conf" % self.name):
            # service is managed by upstart
            self.enable_cmd = location['initctl']
            # set the upstart version based on the output of 'initctl version'
            self.upstart_version = LooseVersion('0.0.0')
            try:
                version_re = re.compile(r'\(upstart (.*)\)')
                rc,stdout,stderr = self.module.run_command('initctl version')
                if rc == 0:
                    res = version_re.search(stdout)
                    if res:
                        self.upstart_version = LooseVersion(res.groups()[0])
            except:
                pass  # we'll use the default of 0.0.0

            if location.get('start', False):
                # upstart -- rather than being managed by one command, start/stop/restart are actual commands
                self.svc_cmd = ''

        elif location.get('rc-service', False):
            # service is managed by OpenRC
            self.svc_cmd = location['rc-service']
            self.enable_cmd = location['rc-update']
            return # already have service start/stop tool too!

        else:
            # service is managed by with SysV init scripts
            if location.get('update-rc.d', False):
                # and uses update-rc.d
                self.enable_cmd = location['update-rc.d']
            elif location.get('insserv', None):
                # and uses insserv
                self.enable_cmd = location['insserv']
            elif location.get('chkconfig', False):
                # and uses chkconfig
                self.enable_cmd = location['chkconfig']

        if self.enable_cmd is None:
            return {
                'succeeded': False,
                'msg': "no service or tool found for: %s" % self.name,
            }

        # If no service control tool selected yet, try to see if 'service' is available
        if self.svc_cmd is None and location.get('service', False):
            self.svc_cmd = location['service']

        # couldn't find anything yet
        if self.svc_cmd is None and not self.svc_initscript_exists:
            return {
                'succeeded': False,
                'msg': 'cannot find \'service\' binary or init script for service,  possible typo in service name?, aborting'
            }

        if location.get('initctl', False):
            self.svc_initctl = location['initctl']

        return { 'succeeded': True }

    def get_service_status(self):
        cmd, rc, status_stdout, status_stderr = self.service_control("status")
        status_results = {
            'cmd': cmd,
            'rc': rc,
            'stdout': status_stdout,
            'stderr': status_stderr
        }

        # if we have decided the service is managed by upstart, we check for some additional output...
        if self.svc_initctl and self.running is None:
            # check the job status by upstart response
            initctl_cmd = "%s status %s" % (self.svc_initctl, self.name)
            initctl_rc, initctl_status_stdout, initctl_status_stderr = self.execute_command(initctl_cmd)
            status_results['initctl'] = {
                'cmd': initctl_cmd,
                'rc': initctl_rc,
                'stdout': initctl_status_stdout,
                'stderr': initctl_status_stderr,
            }
            if "stop/waiting" in initctl_status_stdout:
                self.running = False
            elif "start/running" in initctl_status_stdout:
                self.running = True

        if self.svc_cmd and self.svc_cmd.endswith("rc-service") and self.running is None:
            openrc_cmd = "%s %s status" % (self.svc_cmd, self.quoted_name)
            openrc_rc, openrc_status_stdout, openrc_status_stderr = self.execute_command(openrc_cmd)
            status_results['openrc'] = {
                'cmd': initctl_cmd,
                'rc': initctl_rc,
                'stdout': initctl_status_stdout,
                'stderr': initctl_status_stderr,
            }
            self.running = "started" in openrc_status_stdout
            self.crashed = "crashed" in openrc_status_stderr

        # Prefer a non-zero return code. For reference, see:
        # http://refspecs.linuxbase.org/LSB_4.1.0/LSB-Core-generic/LSB-Core-generic/iniscrptact.html
        if self.running is None and rc in [1, 2, 3, 4, 69]:
            self.running = False

        # if the job status is still not known check it by status output keywords
        # Only check keywords if there's only one line of output (some init
        # scripts will output verbosely in case of error and those can emit
        # keywords that are picked up as false positives
        if self.running is None and status_stdout.count('\n') <= 1:
            # first transform the status output that could irritate keyword matching
            cleanout = status_stdout.lower().replace(self.name.lower(), '')
            if "stop" in cleanout:
                self.running = False
            elif "run" in cleanout:
                self.running = not ("not " in cleanout)
            elif "start" in cleanout and "not " not in cleanout:
                self.running = True
            elif 'could not access pid file' in cleanout:
                self.running = False
            elif 'is dead and pid file exists' in cleanout:
                self.running = False
            elif 'dead but subsys locked' in cleanout:
                self.running = False
            elif 'dead but pid file exists' in cleanout:
                self.running = False

        # if the job status is still not known and we got a zero for the
        # return code, assume here that the service is running
        if self.running is None and rc == 0:
            self.running = True

        # if the job status is still not known check it by special conditions
        if self.running is None:
            if self.name == 'iptables' and "ACCEPT" in status_stdout:
                # iptables status command output is lame
                # TODO: lookup if we can use a return code for this instead?
                self.running = True

        status_results['running'] = self.running
        return status_results

    def service_control(self, action):

        # Decide what command to run
        svc_cmd = ''
        if self.svc_cmd:
            # SysV and OpenRC take the form <cmd> <name> <action>
            svc_cmd = "%s %s" % (self.svc_cmd, self.quoted_name)
        elif self.svc_cmd is None and self.svc_initscript_exists:
            # upstart
            svc_cmd = "%s" % self.svc_initscript

        if svc_cmd != '':
            # upstart or systemd or OpenRC
            cmd = "%s %s" % (svc_cmd, action)
            rc_state, stdout, stderr = self.execute_command(cmd)
        else:
            # SysV
            cmd = "%s %s" % (action, self.quoted_name)
            rc_state, stdout, stderr = self.execute_command(cmd)

        return (cmd, rc_state, stdout, stderr)

    def get_service_enabled(self):

        want = self.enable
        enabled_result = {}
        action = None

        #
        # SysV's chkconfig
        #
        if self.enable_cmd.endswith("chkconfig"):
            cmd = "%s --list %s" % (self.enable_cmd, self.quoted_name)
            (rc, out, err) = self.execute_command(cmd)
            if not self.name in out:
                self.module.fail_json(msg="service %s does not support chkconfig" % self.name)

            got = ("3:on" in out and "5:on" in out)
            enabled_results = {
                'got': got,
                'want': want,
                'changed': got != want,
                'method': "SysV's chkconfig",
                'cmd': cmd,
                'rc': rc,
                'stdout': out,
                'stderr': err,
            }
            return enabled_results

        else:
            self.module.fail_json(msg="not implemented to checkg service is enabled for environments whose enable_cmd=%s" % self.enable_cmd)

    def get_service_defined(self):
        want = self.defined

        #
        # SysV's chkconfig
        #
        if self.enable_cmd.endswith("chkconfig"):
            got = self.svc_initscript_exists
            if got:
                condition = 'initscript %s exists' % self.svc_initscript
            else:
                condition = 'initscript %s not exist' % self.svc_initscript
            defined_results = {
                'got': got,
                'want': want,
                'changed': got != want,
                'method': "SysV's chkconfig",
                'condition': condition,
            }
            return defined_results
        else:
            self.module.fail_json(msg="not implemented to checkg service is defined for environments whose enable_cmd=%s" % self.enable_cmd)

# ===========================================
# Main control flow

def main():
    module = AnsibleModule(
        argument_spec = dict(
            name = dict(required=True),
            state = dict(choices=['started', 'stopped']),
            enabled = dict(type='bool'),
            defined = dict(type='bool'),
            arguments = dict(aliases=['args'], default=''),
        ),
        supports_check_mode=True,
        required_one_of=[['state', 'enabled', 'defined']],
    )

    service = TestService(module)

    module.debug('TestService instantiated - platform %s' % service.platform)
    if service.distribution:
        module.debug('TestService instantiated - distribution %s' % service.distribution)

    result = {
        'name': service.name,
    }

    result['tools'] = service.get_service_tools()
    result['defined'] = service.get_service_defined()
    got_defined = result['defined']['got']
    changed = result['defined']['changed']

    if got_defined:
        if service.module.params['state']:
            result['state'] = service.get_service_status()
            result['state']['got'] = (result['state']['running'] and 'started' or 'stopped')
            result['state']['want'] = service.module.params['state']
            result['state']['changed'] = (result['state']['got'] != result['state']['want'])
            changed = changed or result['state']['changed']

        if 'enabled' in service.module.params:
            result['enabled'] = service.get_service_enabled()
            changed = changed or result['enabled']['changed']

    result['changed'] = changed
    module.exit_json(**result)

from ansible.module_utils.basic import *

main()
