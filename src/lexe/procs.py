from collections.abc import Iterable
from contextlib import contextmanager
import logging
from os import environ
from pathlib import Path
from shlex import quote
from shutil import which
import subprocess
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory

from lexe.config import CLIOpts


log = logging.getLogger(__name__)


class CalledProcessError(subprocess.CalledProcessError):
    @classmethod
    def from_cpe(cls, exc: subprocess.CalledProcessError):
        return cls(
            returncode=exc.returncode,
            cmd=exc.cmd,
            output=exc.output,
            stderr=exc.stderr,
        )

    def __str__(self):
        return super().__str__() + f'\nSTDOUT: {self.stdout}' + f'\nSTDERR: {self.stderr}'


def sub_run(
    *args,
    capture=False,
    returns: None | Iterable[int] = None,
    **kwargs,
) -> CompletedProcess:
    kwargs.setdefault('check', not bool(returns))
    capture = kwargs.setdefault('capture_output', capture)
    args = (*args, *kwargs.pop('args', ()))
    env = kwargs.pop('env', None)
    if env:
        kwargs['env'] = environ | env
    if capture or 'input' in kwargs:
        kwargs.setdefault('text', True)

    try:
        log.debug(f'Running: {" ".join(str(a) for a in args)}')
        result = subprocess.run(args, **kwargs)
        if returns and result.returncode not in returns:
            raise subprocess.CalledProcessError(result.returncode, args[0])
        return result
    except subprocess.CalledProcessError as e:
        if capture:
            raise CalledProcessError.from_cpe(e) from e
        raise
    except Exception as e:
        raise CalledProcessError('n/a', args, '', '') from e


def exe_dev_test_key_fpath() -> Path:
    return Path.home() / '.ssh' / 'id_lexe_exe_dev_tests'


def use_exe_dev_test_key() -> bool:
    return environ.get('LEXE_USE_EXE_DEV_TEST_KEY') == '1'


def legacy_cli_opts() -> CLIOpts | None:
    key_fpath = exe_dev_test_key_fpath()
    if not use_exe_dev_test_key() or not key_fpath.exists():
        return None

    return CLIOpts(
        ssh_ident_fpath=key_fpath,
        ssh_host_key_check=True,
        ssh_known_hosts_manage=True,
    )


def ssh_identity_args(ssh_ident_fpath: Path | None) -> tuple[str | Path, ...]:
    if ssh_ident_fpath is None:
        return ()

    return (
        '-o',
        'IdentitiesOnly=yes',
        '-o',
        'IdentityAgent=none',
        '-i',
        ssh_ident_fpath,
    )


def host_key_args(opts: CLIOpts) -> tuple[str, ...]:
    if not opts.ssh_host_key_check:
        return (
            '-o',
            'StrictHostKeyChecking=no',
            '-o',
            'UserKnownHostsFile=/dev/null',
        )

    if opts.ssh_known_hosts_manage:
        return ('-o', 'StrictHostKeyChecking=accept-new')

    return ()


def effective_cli_opts(opts: CLIOpts | None = None) -> CLIOpts | None:
    return opts or legacy_cli_opts()


def exe_dev_ssh_args(opts: CLIOpts | None = None) -> tuple[str | Path, ...]:
    if (effective_opts := effective_cli_opts(opts)) is None:
        return ()

    return (*host_key_args(effective_opts), *ssh_identity_args(effective_opts.ssh_ident_fpath))


def docker_ssh_command(opts: CLIOpts | None = None) -> str | None:
    if (effective_opts := effective_cli_opts(opts)) is None:
        return None

    ssh_args = ()
    if not effective_opts.ssh_host_key_check:
        ssh_args = (*ssh_args, *host_key_args(effective_opts))
    ssh_args = (*ssh_args, *ssh_identity_args(effective_opts.ssh_ident_fpath))
    if not ssh_args:
        return None

    return 'ssh ' + ' '.join(quote(str(arg)) for arg in ssh_args)


def docker_pussh_args(opts: CLIOpts | None = None) -> tuple[str | Path, ...]:
    if (effective_opts := effective_cli_opts(opts)) is None:
        return ()

    if effective_opts.ssh_ident_fpath is None:
        return ()

    return ('--ssh-key', effective_opts.ssh_ident_fpath)


def docker_pussh_env(opts: CLIOpts | None = None) -> dict[str, str] | None:
    if (effective_opts := effective_cli_opts(opts)) is None:
        return None

    if not effective_opts.ssh_host_key_check:
        return {'SSH_STRICT_HOST_KEY_CHECKING': 'no'}

    return None


def docker_ssh_config_text(remote_host: str, opts: CLIOpts | None = None) -> str | None:
    if (effective_opts := effective_cli_opts(opts)) is None:
        return None

    lines = [f'Host {remote_host}']
    has_custom_settings = False

    if not effective_opts.ssh_host_key_check:
        lines.extend(
            (
                '  StrictHostKeyChecking no',
                '  UserKnownHostsFile /dev/null',
            ),
        )
        has_custom_settings = True
    elif effective_opts.ssh_known_hosts_manage:
        lines.append('  StrictHostKeyChecking accept-new')
        has_custom_settings = True

    if effective_opts.ssh_ident_fpath is not None:
        lines.extend(
            (
                '  IdentitiesOnly yes',
                '  IdentityAgent none',
                f'  IdentityFile {effective_opts.ssh_ident_fpath}',
            ),
        )
        has_custom_settings = True

    if not has_custom_settings:
        return None

    return '\n'.join(lines) + '\n'


@contextmanager
def docker_host_url(remote_host: str, opts: CLIOpts | None = None):
    yield f'ssh://{remote_host}'


@contextmanager
def docker_client_env(remote_host: str, opts: CLIOpts | None = None):
    if (ssh_config_text := docker_ssh_config_text(remote_host, opts)) is None:
        yield {}
        return

    with TemporaryDirectory(prefix='lexe-docker-ssh-') as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        ssh_dpath = tmp_dir / '.ssh'
        ssh_dpath.mkdir(mode=0o700)
        config_fpath = ssh_dpath / 'config'
        config_fpath.write_text(ssh_config_text)
        config_fpath.chmod(0o600)
        bin_dpath = tmp_dir / 'bin'
        bin_dpath.mkdir(mode=0o700)
        wrapper_fpath = bin_dpath / 'ssh'
        ssh_bin = which('ssh') or '/usr/bin/ssh'
        wrapper_fpath.write_text(
            f'#!/bin/sh\nexec {quote(ssh_bin)} -F {quote(str(config_fpath))} "$@"\n',
        )
        wrapper_fpath.chmod(0o700)
        path_value = str(bin_dpath)
        if existing_path := environ.get('PATH'):
            path_value = f'{bin_dpath}:{existing_path}'
        yield {'PATH': path_value}


def is_exe_dev_ssh_destination(arg: object) -> bool:
    return isinstance(arg, str) and (arg == 'exe.dev' or arg.endswith('.exe.xyz'))


def ssh(*args, opts: CLIOpts | None = None, **kwargs):
    if any(is_exe_dev_ssh_destination(arg) for arg in args):
        args = (*exe_dev_ssh_args(opts), *args)
    return sub_run('ssh', args=args, **kwargs)
