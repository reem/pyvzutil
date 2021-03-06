import sys
import sh
import subprocess

from templates import wrap_in_env, wrap_in_vz


__all__ = [
    'LocalRunner',
    'VzRunner',
    'SshRunner',
    'SshToVzRunner',
]


def pse(line):
    "Print a line of output to stderr of the python process."
    sys.stderr.write(line)


class SshToVzRunner(object):

    def __init__(self, ctid, host, user='root', port=22, ssh_options=[]):
        """
        Create a Runner to access a vz container on a remote host.

        Parameters
        ----------
        host : string
            hostname or ip of the target machine
        ctid : int
            ctid of the target machine
        ssh_options : list of flags to ssh
            ssh options, e.g. ['-p', '2222', '-o', 'StrictHostKeyChecking=no']
        """
        self.ssh_runner = SshRunner(host, user, port, ssh_options)
        self.ctid = ctid

    def run(self, commands, quiet=False):
        """
        Run a command or a script of commands on the target machine.
        """
        wrapped_commands = wrap_in_vz(commands, self.ctid)
        return self.ssh_runner.run(wrapped_commands, quiet=quiet)

    def copy_from(self, src, dest, quiet=False):
        """
        Copy from a location `src` on the remote machine to a location
        `dest` on the local machine.
        """
        vz_src = self.get_vz_dir(src)
        return self.ssh_runner.copy_from(vz_src, dest, quiet=quiet)

    def copy_to(self, src, dest, quiet=False):
        """
        Copy from a location `src` on the local machine to a location
        `dest` on the remote machine.
        """
        vz_dest = self.get_vz_dir(dest)
        return self.ssh_runner.copy_to(src, vz_dest, quiet=quiet)

    def interactive(self):
        "Open an interactive shell on the target machine"
        subprocess.call(self.cmd(), shell=True)

    def cmd(self):
        """
        Return as a string the shell command to boot an interactive shell
        on the target
        """
        return "%s vzctl enter %s" % (self.ssh_runner.cmd(), self.ctid)

    def get_vz_dir(self, path):
        """
        Get the directory (relative to the host) corresponding to path
        `path` withing the vz container.
        """
        return '/vz/root/%d/%s' % (self.ctid, path)


class SshRunner(object):

    def __init__(self, host, user='root', port=22, ssh_options=[]):
        """
        Parameters
        ----------
        host : string
            hostname or ip of the target machine
        ssh_options : list of flags to ssh
            ssh options, e.g. ['-p', '2222', '-o', 'StrictHostKeyChecking=no']
        """
        self.host = host
        self.user = user
        self.target = '%s@%s' % (user, host)
        self.port = port
        self.ssh_options = ['-p', '%d' % port]
        self.scp_options = ['-P', '%d' % port]
        self.ssh_options.extend(ssh_options)
        self.scp_options.extend(ssh_options)
        self.ssh = sh.ssh.bake(self.ssh_options)
        self.scp = sh.scp.bake(self.scp_options)

    def run(self, commands, quiet=False):
        "Run a command or a script of commands on the target machine"
        if quiet:
            return self.ssh(self.target, _in=commands)
        else:
            return self.ssh(self.target, _in=commands,
                            _out=pse, _err=pse, _tee=True)

    def copy_from(self, src, dest, quiet=False):
        """
        Copy from a location `src` on the remote machine to a location
        `dest` on the local machine.
        """
        if quiet:
            return self.scp('-r', self.get_scp_dir(src), dest)
        else:
            return self.scp('-r', self.get_scp_dir(src), dest,
                            _out=pse, _err=pse, _tee=True)

    def copy_to(self, src, dest, quiet=False):
        """
        Copy from a location `src` on the local machine to a location
        `dest` on the remote machine.
        """
        if quiet:
            return self.cp('-r', src, self.get_scp_dir(dest))
        else:
            return self.scp('-r', src, self.get_scp_dir(dest),
                            _out=pse, _err=pse, _tee=True)

    def get_scp_dir(self, path):
        return '%s:%s' % (self.target, path)

    def interactive(self):
        "Open an interactive shell on the target machine"
        subprocess.call(self.cmd('ssh'), shell=True)

    def cmd(self, which='ssh'):
        """
        Return as a string the shell command to boot an interactive shell
        on the target
        """
        if which == 'ssh':
            return "ssh %s %s" % (' '.join(self.ssh_options), self.target)
        elif which == 'scp':
            return "scp %s %s" % (' '.join(self.scp_options), self.target)
        else:
            raise ValueError('`which` should be either "ssh" or "scp"')


class VzRunner(object):

    def __init__(self, ctid):
        """
        Parameters
        ----------
        ctid : int
            ctid of the target machine
        """
        self.ctid = ctid

    def run(self, commands, quiet=False):
        """
        Run a command or a script of commands on the target machine.

        The run is with vzctl exec2, so the environment may not be quite right.
        We attempt to define HOME and USER, and source all the usual files, in
        order to minimize this problem.

        """
        wrapped_commands = wrap_in_env(commands)
        if quiet:
            return sh.vzctl('exec2', self.ctid, 'bash', _in=wrapped_commands)
        else:
            return sh.vzctl('exec2', self.ctid, 'bash', _in=wrapped_commands,
                            _out=pse, _err=pse, _tee=True)

    def copy_from(self, src, dest, quiet=False):
        """
        Copy from a location `src` on the remote machine to a location
        `dest` on the local machine.
        """
        if quiet:
            return sh.cp('-r', self.get_vz_dir(src), dest)
        else:
            return sh.cp('-r', self.get_vz_dir(src), dest,
                         _out=pse, _err=pse, _tee=True)

    def copy_to(self, src, dest, quiet=False):
        """
        Copy from a location `src` on the local machine to a location
        `dest` on the remote machine.
        """
        if quiet:
            return sh.cp('-r', src, self.get_vz_dir(dest))
        else:
            return sh.cp('-r', src, self.get_vz_dir(dest),
                         _out=pse, _err=pse, _tee=True)

    def interactive(self):
        "Open an interactive shell on the target machine"
        subprocess.call(self.cmd(), shell=True)

    def cmd(self):
        """
        Return as a string the shell command to boot an interactive shell
        on the target
        """
        return "vzctl enter %s" % self.ctid

    def get_vz_dir(self, path):
        return '/vz/root/%d/%s' % (self.ctid, path)


class LocalRunner(object):

    def __init__(self, ctid):
        """
        Parameters
        ----------
        """
        self.ctid = ctid

    def run(self, commands, quiet=False):
        """
        Run a command or a script of commands on the local machine.

        Obviously this is silly, the point is to have the same api for all
        four environments: local, vz, ssh, and ssh to vz.

        """
        if quiet:
            return sh.bash(_in=commands)
        else:
            return sh.bash(_in=commands,
                           _out=pse, _err=pse, _tee=True)

    def copy_from(self, src, dest, quiet=False):
        """
        Copy from a location `src` on the remote machine to a location
        `dest` on the local machine.
        """
        if quiet:
            return sh.cp('-r', src, dest)
        else:
            return sh.cp('-r', src, dest,
                         _out=pse, _err=pse, _tee=True)

    def copy_to(self, src, dest, quiet=False):
        """
        Copy from a location `src` on the local machine to a location
        `dest` on the remote machine.
        """
        if quiet:
            return sh.cp('-r', src, dest)
        else:
            return sh.cp('-r', src, dest,
                         _out=pse, _err=pse, _tee=True)

    def interactive(self):
        "Open an interactive shell on the target machine"
        subprocess.call(self.cmd(), shell=True)

    def cmd(self):
        """
        Return as a string the shell command to boot an interactive shell
        on the target
        """
        return "bash"
