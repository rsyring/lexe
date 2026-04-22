from unittest.mock import patch

from click.testing import CliRunner

import lexe.cli
from lexe.cli import main


class TestProvision:
    def test_command(self, tmp_path, monkeypatch):
        config_fpath = tmp_path / 'lexe.yaml'
        config_fpath.write_text('project:\n  name: demo\n  vm-host: demo-vm\nservices:\n  web:\n')

        seen = {}

        class FakeProvision:
            def __init__(self, config_opts):
                seen['config_opts'] = config_opts

            def run(self):
                seen['ran'] = True

        monkeypatch.setattr(lexe.cli, 'Provision', FakeProvision)

        result = CliRunner().invoke(main, ['--config-fpath', str(config_fpath), 'provision'])

        assert result.exit_code == 0
        assert seen['ran'] is True
        assert seen['config_opts'].config.project.name == 'demo'
        assert seen['config_opts'].config.project.vm_host == 'demo-vm'
        assert seen['config_opts'].config.project.path == tmp_path


class TestDestroy:
    def test_command(self, tmp_path, monkeypatch):
        config_fpath = tmp_path / 'lexe.yaml'
        config_fpath.write_text('project:\n  name: demo\n  vm-host: demo-vm\nservices:\n  web:\n')

        seen = {}

        class FakeDestroy:
            def __init__(self, config_opts):
                seen['config_opts'] = config_opts

            def run(self):
                seen['ran'] = True

        monkeypatch.setattr(lexe.cli, 'Destroy', FakeDestroy)

        result = CliRunner().invoke(main, ['--config-fpath', str(config_fpath), 'destroy'])

        assert result.exit_code == 0
        assert seen['ran'] is True
        assert seen['config_opts'].config.project.name == 'demo'
        assert seen['config_opts'].config.project.vm_host == 'demo-vm'


class TestDeploy:
    def test_command(self, tmp_path, monkeypatch):
        config_fpath = tmp_path / 'lexe.yaml'
        config_fpath.write_text('project:\n  name: demo\n  vm-host: demo-vm\nservices:\n  web:\n')

        seen = {}

        class FakeDeploy:
            def __init__(self, config_opts, allow_dirty, restart_all):
                seen['config_opts'] = config_opts
                seen['allow_dirty'] = allow_dirty
                seen['restart_all'] = restart_all

            def run(self):
                seen['ran'] = True

        monkeypatch.setattr(lexe.cli, 'Deploy', FakeDeploy)

        result = CliRunner().invoke(
            main,
            ['--config-fpath', str(config_fpath), 'deploy', '--allow-dirty', '--restart-all'],
        )

        assert result.exit_code == 0
        assert seen['ran'] is True
        assert seen['config_opts'].config.project.name == 'demo'
        assert seen['config_opts'].config.project.vm_host == 'demo-vm'
        assert seen['config_opts'].config.project.path == tmp_path
        assert seen['allow_dirty'] is True
        assert seen['restart_all'] is True


class TestStatus:
    def test_command(self, tmp_path):
        config_fpath = tmp_path / 'lexe.yaml'
        config_fpath.write_text('project:\n  name: demo\n  vm-host: demo-vm\nservices:\n  web:\n')

        seen = {}

        class FakeStatus:
            def __init__(self, config_opts):
                seen['config_opts'] = config_opts

            def run(self):
                seen['ran'] = True

        with patch.object(lexe.cli, 'Status', FakeStatus):
            result = CliRunner().invoke(main, ['--config-fpath', str(config_fpath), 'status'])

        assert result.exit_code == 0
        assert seen['ran'] is True
        assert seen['config_opts'].config.project.name == 'demo'
        assert seen['config_opts'].config.project.vm_host == 'demo-vm'
        assert seen['config_opts'].config.project.path == tmp_path

    def test_invalid_known_hosts_combo(self, tmp_path):
        config_fpath = tmp_path / 'lexe.yaml'
        config_fpath.write_text('project:\n  name: demo\n  vm-host: demo-vm\nservices:\n  web:\n')

        result = CliRunner().invoke(
            main,
            [
                '--config-fpath',
                str(config_fpath),
                '--no-ssh-host-key-check',
                '--ssh-known-hosts-manage',
                'status',
            ],
        )

        assert result.exit_code != 0
        assert '--ssh-known-hosts-manage requires --ssh-host-key-check' in result.output
