from __future__ import annotations

import os
from pathlib import Path

from serde import field, from_dict, serde
import yaml


def find_upwards(d: Path, filename: str):
    root = Path(d.root)

    while d != root:
        attempt = d / filename
        if attempt.exists():
            return attempt
        d = d.parent

    return None


@serde
class LexeConfig:
    app_name: str = field(rename='app-name')
    vm_host_name: str = field(rename='vm-host-name')
    public_service: str | None = field(default=None, rename='public-service')

    @classmethod
    def from_yaml(cls, yaml_fpath: os.PathLike) -> LexeConfig:
        config = yaml.safe_load(Path(yaml_fpath).read_text())
        return from_dict(LexeConfig, config)

    @classmethod
    def find_lexe(cls, start_at: Path) -> LexeConfig:
        if start_at.is_dir():
            config_fpath = find_upwards(start_at, 'lexe.yaml')

            if config_fpath is None:
                raise ValueError(f'No lexe.yaml in {start_at} or parents')

        elif start_at.suffix == '.yaml':
            config_fpath = start_at

        else:
            raise ValueError(f'{start_at} should be a directory or .yaml file')

        return cls.from_yaml(config_fpath)
