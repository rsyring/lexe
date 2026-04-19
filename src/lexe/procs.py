from collections.abc import Iterable
import logging
from os import environ
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


def ssh(*args, **kwargs):
    return sub_run('ssh', args=args, **kwargs)
