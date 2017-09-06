#!/usr/bin/python
# -*- coding: utf-8 -*-

DOCUMENTATION = """
---
module: conda
short_description: Manage Python libraries via conda
description:
  >
    Manage Python libraries via conda.
    Can install, update, and remove packages.
author: Synthicity
notes:
  >
    Requires conda to already be installed.
    Will look under the home directory for a conda executable.
options:
  name:
    description: The name of a Python library to install
    required: true
    default: null
  version:
    description: A specific version of a library to install
    required: false
    default: null
  state:
    description: State in which to leave the Python package
    required: false
    default: present
    choices: [ "present", "absent", "latest" ]
  channels:
    description: Extra channels to use when installing packages
    required: false
    default: null
  executable:
    description: Full path to the conda executable
    required: false
    default: null
  extra_args:
    description: Extra arguments passed to conda
    required: false
    default: null
"""

EXAMPLES = """
- name: install numpy via conda
  conda: name=numpy state=latest

- name: install scipy 0.14 via conda
  conda: name=scipy version="0.14"

- name: remove matplotlib from conda
  conda: name=matplotlib state=absent
"""

from distutils.spawn import find_executable
import os.path
import json
from ansible.module_utils.basic import AnsibleModule


def _find_conda(module, executable):
    """
    If `executable` is not None, checks whether it points to a valid file
    and returns it if this is the case. Otherwise tries to find the `conda`
    executable in the path. Calls `fail_json` if either of these fail.
    """
    if not executable:
        conda = find_executable('conda')
        if conda:
            return conda
    else:
        if os.path.isfile(executable):
            return executable

    module.fail_json(msg="could not find conda executable")


def add_channels_to_command(command, channels):
    """
    Add extra channels to a conda command by splitting the channels
    and putting "--channel" before each one.
    """
    if channels:
        channels = channels.strip().split()
        dashc = []
        for channel in channels:
            dashc.append('--channel')
            dashc.append(channel)

        return command[:2] + dashc + command[2:]
    else:
        return command


def add_extras_to_command(command, extras):
    """
    Add extra arguments to a conda command by splitting the arguments
    on white space and inserting them after the second item in the command.
    """
    if extras:
        extras = extras.strip().split()
        return command[:2] + extras + command[2:]
    else:
        return command


def parse_conda_stdout(stdout):
    """
    Parses the given output from Conda.
    :param stdout: the output from stdout
    :return: standard out as parsed JSON else `None` if non-JSON format
    """
    # Conda spews loading progress reports onto stdout(!?), which need ignoring. Bug observed in Conda version 4.3.25.
    split_lines = stdout.strip().split("\n")
    while len(split_lines) > 0:
        line = split_lines.pop(0)
        try:
            line_content = json.loads(line)
            if "progress" not in line_content and "maxval" not in line_content:
                # Looks like this was the output, not a progress update
                return line_content
        except ValueError:
            split_lines.insert(0, line)
            break

    try:
        return json.loads("".join(split_lines))
    except ValueError:
        return None


def _run_conda_command(module, command):
    """
    Runs the given Conda related command.

    It is assumed that the command will return JSON.
    :param module: the Ansible module
    :param command: the command to run
    :return: tuple where the first element is the parsed JSON output returned by Conda and the second is what was
    written to standard error
    :raises CondaCommandError: if there a problem running Conda
    """
    command = add_channels_to_command(command, module.params['channels'])
    command = add_extras_to_command(command, module.params['extra_args'])

    rc, stdout, stderr = module.run_command(command)
    parsed_stdout = parse_conda_stdout(stdout)

    if rc != 0 or parsed_stdout is None:
        error_message = None
        if parsed_stdout is not None and 'message' in parsed_stdout:
            error_message = parsed_stdout['message']
        raise CondaCommandError(command, error_message, parsed_stdout, stdout, stderr)

    return parsed_stdout, stderr


def _run_conda_package_command(module, name, version, command):
    """
    Runs a Conda command related to a particular package.
    :param module: the Ansible module
    :param name: the name of the package the command refers to
    :param version: the version of the package that the command is referring to
    :param command: the Conda command
    :raises CondaPackageNotFoundError: if the package referred to by this command is not found
    """
    try:
        return _run_conda_command(module, command)
    except CondaCommandError as e:
        if e.output is not None and 'exception_name' in e.output \
                and e.output['exception_name'] == 'PackageNotFoundError':
            raise CondaPackageNotFoundError(name, version)
        else:
            raise


def get_install_target(name, version):
    """
    Gets install target string for a package with the given name and version.
    :param name: the package name
    :param version: the package version (`None` if latest)
    :return: the target string that Conda can refer to the given package as
    """
    install_target = name
    if version is not None:
        install_target = '%s=%s' % (name, version)
    return install_target


def _check_package_installed(module, conda, name, version):
    """
    Check whether a package with the given name and version is installed.
    :param module: the Ansible module
    :param name: the name of the package to check if installed
    :param version: the version of the package to check if installed (`None` if check for latest)
    :return: `True` if a package with the given name and version is installed
    :raises CondaUnexpectedOutputError: if the JSON returned by Conda was unexpected
    """
    output, stderr = _run_conda_package_command(
        module, name, version, [conda, 'install', '--json', '--dry-run', get_install_target(name, version)])

    if 'message' in output and output['message'] == 'All requested packages already installed.':
        return True
    elif 'actions' in output and len(output['actions']) > 0:
        return False
    else:
        raise CondaUnexpectedOutputError(output, stderr)


def _install_package(module, conda, name, version=None):
    """
    Install a package with the given name and version. Version will default to latest if `None`.
    """
    command = [conda, 'install', '--yes', '--json', get_install_target(name, version)]
    if module.check_mode:
        command.insert(-1, '--dry-run')

    output, stderr = _run_conda_package_command(module, name, version, command)
    module.exit_json(changed=True, name=name, version=version, output=output, error=stderr)


def _uninstall_package(module, conda, name):
    """
    Use Conda to remove a package with the given name.
    """
    command = [conda, 'remove', '--yes', '--json', name]
    if module.check_mode:
        command.insert(-1, '--dry-run')

    output, stderr = _run_conda_package_command(module, name, None, command)
    module.exit_json(changed=True, output=output, error=stderr)


class CondaCommandError(Exception):
    """
    Error raised when a Conda command fails.
    """
    def __init__(self, command, error_message, output, stdout, stderr):
        self.command = command
        self.error_message = error_message
        self.output = output
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        error_message = ' Error: %s.' % self.error_message if self.error_message is not None else ''
        stdout = ' stdout: %s.' % self.stdout if self.error_message is None and self.stdout.strip() != '' else ''
        stderr = ' stderr: %s.' % self.stderr if self.stderr.strip() != '' else ''
        return 'Error running command: %s.%s%s%s' % (self.command, error_message, stdout, stderr)


class CondaPackageNotFoundError(Exception):
    """
    Error raised when a Conda package has not been found in the package repositories that were searched.
    """
    def __int__(self, name, version):
        self.name = name
        self.version = version

    def __str__(self):
        return 'Conda package "%s" not found' % (get_install_target(self.name, self.version))


class CondaUnexpectedOutputError(Exception):
    """
    Error raised when the running of a Conda command has resulted in an unexpected output.
    """
    def __int__(self, output, stderr):
        self.output = output
        self.stderr = stderr

    def __str__(self):
        stderr = 'stderr: %s' % self.stderr if self.stderr.strip() != '' else ''
        return 'Unexpected output from Conda (may be due to a change in Conda\'s output format): "%output".%s' \
               % (self.output, stderr)


def main():
    """
    Entrypoint.
    """
    module = AnsibleModule(
        argument_spec={
            'name': {'required': True, 'type': 'str'},
            'version': {'default': None, 'required': False, 'type': 'str'},
            'state': {
                'default': 'present',
                'required': False,
                'choices': ['present', 'absent', 'latest']
            },
            'channels': {'default': None, 'required': False},
            'executable': {'default': None, 'required': False},
            'extra_args': {'default': None, 'required': False, 'type': 'str'}
        },
        supports_check_mode=True)

    conda = _find_conda(module, module.params['executable'])
    name = module.params['name']
    state = module.params['state']
    version = module.params['version']

    if state == 'latest' and version is not None:
        module.fail_json(msg='`version` must not be set if `state == "latest"` (`latest` upgrades to newest version)')

    correct_version_installed = _check_package_installed(module, conda, name, version)

    if not correct_version_installed and state != 'absent':
        _install_package(module, conda, name, version)

    if state == 'absent':
        try:
            _uninstall_package(module, conda, name)
        except CondaPackageNotFoundError:
            """ EAFP """

    module.exit_json(changed=False)


if __name__ == '__main__':
    main()
