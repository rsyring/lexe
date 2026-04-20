from pydantic_core import ErrorDetails


class LexeException(Exception): ...


class LexeError(LexeException): ...


class ConfigError(LexeError):
    _errors: list[ErrorDetails]

    def __init__(self, errors: list[ErrorDetails]) -> None:
        self._errors = errors

    def error_msg(self, err: ErrorDetails):
        loc = '.'.join(err['loc'])
        msg = err['msg']
        msg_type = err['type']
        if msg_type == 'missing':
            msg = msg_type
        if loc == 'services' and msg_type == 'too_short':
            msg = 'at least one service is required'
        return f'{loc}: {msg}'

    def errors(self):
        return [self.error_msg(err) for err in self._errors]
