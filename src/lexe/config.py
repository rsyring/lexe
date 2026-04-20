from __future__ import annotations

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
import yaml

from .exc import ConfigError


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


HookCommand = str | list[str]


def _normalize_hook_commands(value: object) -> list[HookCommand]:
    if value is None:
        return []

    if isinstance(value, str):
        return [value]

    if not isinstance(value, list):
        raise ValueError('hook commands must be a string, list[str], or list[list[str]]')

    if all(isinstance(item, str) for item in value):
        return value

    if all(isinstance(item, list) and all(isinstance(arg, str) for arg in item) for item in value):
        return value

    raise ValueError('hook commands must be a string, list[str], or list[list[str]]')


class LexeBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class ProjectConfig(LexeBaseModel):
    path: Path
    name: str
    vm_host: str = Field(alias='vm-host')


class PublicConfig(LexeBaseModel):
    port: int | None = None
    healthcheck_url: str | None = Field(default=None, alias='healthcheck-url')


class ServiceHooksConfig(LexeBaseModel):
    start_pre: list[HookCommand] = Field(default_factory=list, alias='start-pre')
    start_post: list[HookCommand] = Field(default_factory=list, alias='start-post')

    @field_validator('start_pre', 'start_post', mode='before')
    @classmethod
    def normalize_hook_commands(cls, value: object) -> list[HookCommand]:
        return _normalize_hook_commands(value)


class ServiceConfig(LexeBaseModel):
    deploy: str = 'always'
    hooks: ServiceHooksConfig = Field(default_factory=ServiceHooksConfig)

    @model_validator(mode='before')
    @classmethod
    def none_to_empty_dict(cls, value: object) -> object:
        if value is None:
            return {}

        return value


class DeployHooksConfig(LexeBaseModel):
    deploy_pre: list[HookCommand] = Field(default_factory=list, alias='deploy-pre')
    deploy_post: list[HookCommand] = Field(default_factory=list, alias='deploy-post')

    @field_validator('deploy_pre', 'deploy_post', mode='before')
    @classmethod
    def normalize_hook_commands(cls, value: object) -> list[HookCommand]:
        return _normalize_hook_commands(value)


class LexeConfig(LexeBaseModel):
    project: ProjectConfig
    public: PublicConfig | None = None
    services: dict[str, ServiceConfig] = Field(min_length=1)
    hooks: DeployHooksConfig = Field(default_factory=DeployHooksConfig)

    @classmethod
    def from_yaml(cls, yaml_fpath: Path) -> Self:
        config = yaml.safe_load(yaml_fpath.read_text()) or {}
        if not isinstance(config, dict):
            raise ValueError('lexe.yaml format is invalid, check docs for example config')

        if isinstance(config.get('project'), dict):
            config['project']['path'] = yaml_fpath.parent

        try:
            return cls.model_validate(config)
        except ValidationError as e:
            raise ConfigError(e.errors()) from e

    @classmethod
    def find_lexe(cls, start_at: Path) -> Self:
        return cls.from_yaml(find_lexe_fpath(start_at))
