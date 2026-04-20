from pathlib import Path

import pytest

from lexe.config import ConfigError, LexeConfig


configs_dpath = Path(__file__).parent / 'configs'


def config_yaml(fname: str):
    return LexeConfig.from_yaml(configs_dpath / fname)


class TestLexeConfig:
    def test_basic(self):
        config = config_yaml('basic.yaml')

        assert config.project.name == 'ncc1701d'
        assert config.project.vm_host == 'ncc1701d-starfleet'

        assert config.public.port == 8000
        assert config.public.healthcheck_url == 'https://ncc1701d-starfleet.exe.xyz/healthy'

        assert set(config.services) == {'db', 'schedule', 'web'}

        assert config.services['db'].deploy == 'contingent'
        assert config.services['db'].hooks.start_pre == []
        assert config.services['db'].hooks.start_post == []

        assert config.services['schedule'].deploy == 'always'
        assert config.services['schedule'].hooks.start_pre == []
        assert config.services['schedule'].hooks.start_post == []

        assert config.services['web'].deploy == 'always'
        assert config.services['web'].hooks.start_pre == ['python hooks/log-event.py']
        assert config.services['web'].hooks.start_post == ['python hooks/log-event.py']

        assert config.hooks.deploy_pre == []
        assert config.hooks.deploy_post == []

    def test_hooks_without_public(self):
        config = config_yaml('hooks.yaml')

        assert config.public is None

        assert config.services['str-single'].hooks.start_pre == ['echo foo']
        assert config.services['str-single'].hooks.start_post == []

        assert config.services['str-multi'].hooks.start_pre == []
        assert config.services['str-multi'].hooks.start_post == ['echo foo', 'echo bar']

        assert config.services['arg-multi'].hooks.start_pre == [
            ['echo', 'foo'],
            ['echo', 'bar'],
        ]
        assert config.services['arg-multi'].hooks.start_post == []

        assert config.hooks.deploy_pre == ['python hooks/log-event.py']
        assert config.hooks.deploy_post == ['python hooks/log-event.py']

        config = config_yaml('hooks2.yaml')
        assert config.hooks.deploy_pre == [['echo', 'foo']]

    def test_project_required(self):
        with pytest.raises(ConfigError) as raised:
            config_yaml('project-missing.yaml')

        assert raised.value.errors() == [
            'project: missing',
        ]

    def test_services_required(self):
        with pytest.raises(ConfigError) as raised:
            config_yaml('services-missing.yaml')

        assert raised.value.errors() == [
            'services: missing',
        ]

    def test_services_must_not_be_empty(self):
        with pytest.raises(ConfigError) as raised:
            config_yaml('services-empty.yaml')

        assert raised.value.errors() == [
            'services: at least one service is required',
        ]
