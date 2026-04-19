from collections.abc import Iterable
import logging
from os import environ
from pathlib import Path
import subprocess
from subprocess import CompletedProcess


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


def exe_dev_ssh_args() -> tuple[str | Path, ...]:
    key_fpath = exe_dev_test_key_fpath()
    if not use_exe_dev_test_key() or not key_fpath.exists():
        return ()

    return (
        '-o',
        'IdentitiesOnly=yes',
        '-o',
        'IdentityAgent=none',
        '-i',
        key_fpath,
    )


def docker_ssh_command() -> str | None:
    key_fpath = exe_dev_test_key_fpath()
    if not use_exe_dev_test_key() or not key_fpath.exists():
        return None

    return (
        'ssh '
        '-o StrictHostKeyChecking=accept-new '
        '-o IdentitiesOnly=yes '
        '-o IdentityAgent=none '
        f'-i {key_fpath}'
    )


def is_exe_dev_ssh_destination(arg: object) -> bool:
    return isinstance(arg, str) and (arg == 'exe.dev' or arg.endswith('.exe.xyz'))


def ssh(*args, **kwargs):
    if args and is_exe_dev_ssh_destination(args[0]):
        args = (*exe_dev_ssh_args(), *args)
    return sub_run('ssh', args=args, **kwargs)
