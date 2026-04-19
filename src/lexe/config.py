from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any

import yaml


def find_upwards(d: Path, filename: str) -> Path | None:
    root = Path(d.root)

    while d != root:
        attempt = d / filename
        if attempt.exists():
            return attempt
        d = d.parent

    return None


def find_lexe_fpath(start_at: Path) -> Path:
    if start_at.is_dir():
        config_fpath = find_upwards(start_at, 'lexe.yaml')

        if config_fpath is None:
            raise ValueError(f'No lexe.yaml in {start_at} or parents')

    elif start_at.suffix == '.yaml':
        config_fpath = start_at

    else:
        raise ValueError(f'{start_at} should be a directory or .yaml file')

    return config_fpath


@dataclass(frozen=True)
class Hook:
    service: str
    command: str | tuple[str, ...]

    @classmethod
    def from_raw(cls, raw: object, *, default_service: str) -> Hook:
        if isinstance(raw, str):
            return cls(service=default_service, command=raw)

        if isinstance(raw, list):
            if not raw or not all(isinstance(item, str) for item in raw):
                raise ValueError('Hook command lists must be non-empty lists of strings.')
            return cls(service=default_service, command=tuple(raw))

        if isinstance(raw, dict):
            service = raw.get('service', default_service)
            if not isinstance(service, str) or not service:
                raise ValueError('Hook service must be a non-empty string.')
            if 'command' not in raw:
                raise ValueError('Hook mappings must include a command field.')

            command = cls.from_raw(raw['command'], default_service=service).command
            return cls(service=service, command=command)

        raise ValueError('Hook values must be a string, list of strings, or mapping.')

    def compose_run_args(self) -> tuple[str, ...]:
        if isinstance(self.command, str):
            return ('--entrypoint', 'sh', self.service, '-lc', self.command)
        return ('--entrypoint', self.command[0], self.service, *self.command[1:])

    def display_command(self) -> str:
        if isinstance(self.command, str):
            return self.command
        return ' '.join(self.command)


def parse_hooks(raw: object, *, default_service: str) -> tuple[Hook, ...]:
    if raw is None:
        return ()

    if isinstance(raw, (str, dict)):
        return (Hook.from_raw(raw, default_service=default_service),)

    if isinstance(raw, list):
        if raw and all(isinstance(item, str) for item in raw):
            return (Hook.from_raw(raw, default_service=default_service),)
        return tuple(Hook.from_raw(item, default_service=default_service) for item in raw)

    raise ValueError('Hook phase values must be a command or list of commands.')


@dataclass(frozen=True)
class HookConfig:
    pre_start: tuple[Hook, ...] = ()
    post_start: tuple[Hook, ...] = ()

    @classmethod
    def from_raw(cls, raw: object, *, default_service: str) -> HookConfig:
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise ValueError('hooks must be a mapping.')

        return cls(
            pre_start=parse_hooks(raw.get('pre-start'), default_service=default_service),
            post_start=parse_hooks(raw.get('post-start'), default_service=default_service),
        )


@dataclass(frozen=True)
class LexeConfig:
    app_name: str
    vm_host_name: str
    public_service: str | None = None
    healthcheck_url: str | None = None
    hooks: HookConfig = field(default_factory=HookConfig)

    @property
    def default_service(self) -> str:
        return self.public_service or 'web'

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> LexeConfig:
        public_service = payload.get('public-service')
        healthcheck_url = payload.get('healthcheck-url')

        if public_service is not None and not isinstance(public_service, str):
            raise ValueError('public-service must be a string when set.')
        if healthcheck_url is not None and not isinstance(healthcheck_url, str):
            raise ValueError('healthcheck-url must be a string when set.')

        return cls(
            app_name=payload['app-name'],
            vm_host_name=payload['vm-host-name'],
            public_service=public_service,
            healthcheck_url=healthcheck_url,
            hooks=HookConfig.from_raw(
                payload.get('hooks'),
                default_service=public_service or 'web',
            ),
        )

    @classmethod
    def from_yaml(cls, yaml_fpath: os.PathLike) -> LexeConfig:
        config = yaml.safe_load(Path(yaml_fpath).read_text()) or {}
        if not isinstance(config, dict):
            raise ValueError('lexe.yaml must contain a mapping at the top level.')
        return cls.from_mapping(config)

    @classmethod
    def find_lexe(cls, start_at: Path) -> LexeConfig:
        return cls.from_yaml(find_lexe_fpath(start_at))
