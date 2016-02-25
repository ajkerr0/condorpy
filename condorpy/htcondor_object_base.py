# Copyright (c) 2015 Scott Christensen
#
# This file is part of condorpy
#
# condorpy is free software: you can redistribute it and/or modify it under
# the terms of the BSD 2-Clause License. A copy of the BSD 2-Clause License
# should have been distributed with this file.

import os
import re
import uuid
import subprocess

from logger import log
from exceptions import HTCondorError

from tethyscluster.sshutils import SSHClient
from tethyscluster.exception import RemoteCommandFailed, SSHError

class HTCondorObjectBase(object):
    """

    """

    def __init__(self,
                 host=None,
                 username=None,
                 password=None,
                 private_key=None,
                 private_key_pass=None,
                 remote_input_files=None,
                 working_directory='.'):
        """


        """
        object.__setattr__(self, '_cluster_id', 0)
        object.__setattr__(self, '_remote', None)
        object.__setattr__(self, '_remote_input_files', remote_input_files or None)
        object.__setattr__(self, '_cwd', working_directory)
        if host:
            object.__setattr__(self, '_remote', SSHClient(host, username, password, private_key, private_key_pass))
            object.__setattr__(self, '_remote_id', uuid.uuid4().hex)

    @property
    def cluster_id(self):
        """
        The id assigned to the job (called a cluster in HTConodr) when the job is submitted.
        """
        return self._cluster_id

    @property
    def scheduler(self):
        """
        The remote scheduler where the job/workflow will be submitted
        """
        return self._remote

    @scheduler.setter
    def scheduler(self, host, username='root', password=None, private_key=None, private_key_pass=None):
        """
        Defines the remote scheduler

        Args:
            host (str): the hostname or ip address of the remote scheduler
            username (str, optional): the username used to connect to the remote scheduler. Default is 'root'
            password (str, optional): the password for username on the remote scheduler. Either the password or the private_key must be defined. Default is None.
            private_key (str, optional): the path to the private ssh key used to connect to the remote scheduler. Either the password or the private_key must be defined. Default is None.
            private_key_pass (str, optional): the passphrase for the private_key. Default is None.

        Returns:
            An SSHClient representing the remote scheduler.
        """
        object.__setattr__(self, '_remote', SSHClient(host, username, password, private_key, private_key_pass))

    @property
    def remote_input_files(self):
        """A list of paths to files or directories to be copied to a remote server for remote job submission.

        """
        return self._remote_input_files

    @remote_input_files.setter
    def remote_input_files(self, files):
        """A list of paths to files or directories to be copied to a remote server for remote job submission.

        Args:
            files (list or tuple of strings): A list or tuple of file paths to all input files and the executable that
            are required to be copied to the remote server when submitting the job remotely.

        Note:
            File paths defined for remote_input_files should be relative to the job's working directory on the
            client machine. They are copied into the working directory on the remote. Input file paths defined for
            the submit description file should be relative to the initial directory on the remote server.

        """
        self._remote_input_files = list(files)

    def set_cwd(fn):
        """
        Decorator to set the specified working directory to execute the function, and then restore the previous cwd.
        """
        def wrapped(self, *args, **kwargs):
            log.info('Calling function: %s with args=%s', fn, args if args else [])
            cwd = os.getcwd()
            log.info('Saved cwd: %s', cwd)
            os.chdir(self._cwd)
            log.info('Changing working directory to: %s', self._cwd)
            result = fn(self, *args, **kwargs)
            os.chdir(cwd)
            log.info('Restored working directory to: %s', os.getcwd())
            return result
        return wrapped

    def submit(self, args):
        """


        """
        out, err = self._execute(args)
        if err:
            if re.match('WARNING',err):
                log.warning(err)
            else:
                raise HTCondorError(err)
        log.info(out)
        try:
            self._cluster_id = int(re.search('(?<=cluster |\*\* Proc )(\d*)', out).group(1))
        except:
            self._cluster_id = -1
        return self.cluster_id

    def sync_remote_output(self):
        """Sync the initial directory containing the output and log files with the remote server.

        """
        self._copy_output_from_remote()

    def close_remote(self):
        """Cleans up and closes connection to remote server if defined.

        """
        if self._remote:
            self.remove()
            self._remote.execute('rm -rf %s' % (self._remote_id,))
            self._remote.close()
            del self._remote

    @set_cwd
    def _execute(self, args):
        out = None
        err = None
        if self._remote:
            log.info('Executing remote command %s', ' '.join(args))
            cmd = ' '.join(args)
            try:
                cmd = 'cd %s && %s' % (self._remote_id, cmd)
                out = '\n'.join(self._remote.execute(cmd))
            except RemoteCommandFailed as e:
                err = e.output
            except SSHError as e:
                err = e.msg
        else:
            log.info('Executing local command %s', ' '.join(args))
            process = subprocess.Popen(args, stdout = subprocess.PIPE, stderr=subprocess.PIPE)
            out,err = process.communicate()

        log.info('Execute results - out: %s, err: %s', out, err)
        return out, err

    @set_cwd
    def _copy_input_files_to_remote(self):
        self._remote.put(self.remote_input_files, self._remote_id)

    @set_cwd
    def _copy_output_from_remote(self):
        self._remote.get(os.path.join(self._remote_id, self.initial_dir))

    @set_cwd
    def _open(self, file_name, mode='w'):
        if self._remote:
            return self._remote.remote_file(os.path.join(self._remote_id,file_name), mode)
        else:
            return open(file_name, mode)

    @set_cwd
    def _make_dir(self, dir_name):
        try:
            log.info('making directory %s', dir_name)
            if self._remote:
                self._remote.makedirs(os.path.join(self._remote_id,dir_name))
            else:
                os.makedirs(dir_name)
        except OSError:
            log.warn('Unable to create directory %s. It may already exist.', dir_name)