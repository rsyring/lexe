from unittest.mock import patch

from click.testing import CliRunner

import lexe.cli
from lexe.cli import main


class TestProvision:
    def test_command(self, tmp_path, monkeypatch):
        config_fpath = tmp_path / 'lexe.yaml'
        config_fpath.write_text('app-name: demo\nvm-host-name: demo-vm\n')

        seen = {}

        class FakeProvision:
            def __init__(self, config, app_dpath):
                seen['config'] = config
                seen['app_dpath'] = app_dpath

            def run(self):
                seen['ran'] = True

        monkeypatch.setattr(lexe.cli, 'Provision', FakeProvision)

        result = CliRunner().invoke(main, ['provision', '--config-fpath', str(config_fpath)])

        assert result.exit_code == 0
        assert seen['ran'] is True
        assert seen['config'].app_name == 'demo'
        assert seen['config'].vm_host_name == 'demo-vm'
        assert seen['app_dpath'] == tmp_path


class TestDestroy:
    def test_command(self, tmp_path, monkeypatch):
        config_fpath = tmp_path / 'lexe.yaml'
        config_fpath.write_text('app-name: demo\nvm-host-name: demo-vm\n')

        seen = {}

        class FakeDestroy:
            def __init__(self, config):
                seen['config'] = config

            def run(self):
                seen['ran'] = True

        monkeypatch.setattr(lexe.cli, 'Destroy', FakeDestroy)

        result = CliRunner().invoke(main, ['destroy', '--config-fpath', str(config_fpath)])

        assert result.exit_code == 0
        assert seen['ran'] is True
        assert seen['config'].app_name == 'demo'
        assert seen['config'].vm_host_name == 'demo-vm'


class TestDeploy:
    def test_command(self, tmp_path, monkeypatch):
        config_fpath = tmp_path / 'lexe.yaml'
        config_fpath.write_text('app-name: demo\nvm-host-name: demo-vm\n')

        seen = {}

        class FakeDeploy:
            def __init__(self, config, app_dpath, allow_dirty):
                seen['config'] = config
                seen['app_dpath'] = app_dpath
                seen['allow_dirty'] = allow_dirty

            def run(self):
                seen['ran'] = True

        monkeypatch.setattr(lexe.cli, 'Deploy', FakeDeploy)

        result = CliRunner().invoke(
            main,
            ['deploy', '--config-fpath', str(config_fpath), '--allow-dirty'],
        )

        assert result.exit_code == 0
        assert seen['ran'] is True
        assert seen['config'].app_name == 'demo'
        assert seen['config'].vm_host_name == 'demo-vm'
        assert seen['app_dpath'] == tmp_path
        assert seen['allow_dirty'] is True


class TestStatus:
    def test_command(self, tmp_path):
        config_fpath = tmp_path / 'lexe.yaml'
        config_fpath.write_text('app-name: demo\nvm-host-name: demo-vm\n')

        seen = {}

        class FakeStatus:
            def __init__(self, config, app_dpath):
                seen['config'] = config
                seen['app_dpath'] = app_dpath

            def run(self):
                seen['ran'] = True

        with patch.object(lexe.cli, 'Status', FakeStatus):
            result = CliRunner().invoke(main, ['status', '--config-fpath', str(config_fpath)])

        assert result.exit_code == 0
        assert seen['ran'] is True
        assert seen['config'].app_name == 'demo'
        assert seen['config'].vm_host_name == 'demo-vm'
        assert seen['app_dpath'] == tmp_path
