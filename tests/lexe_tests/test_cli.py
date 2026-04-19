from click.testing import CliRunner

import lexe.cli
from lexe.cli import main


def test_main_provision(tmp_path, monkeypatch):
    config_fpath = tmp_path / 'lexe.yaml'
    config_fpath.write_text('app-name: demo\nvm-host-name: demo-vm\n')

    seen = {}

    class FakeProvision:
        def __init__(self, config):
            seen['config'] = config

        def run(self):
            seen['ran'] = True

    monkeypatch.setattr(lexe.cli, 'Provision', FakeProvision)

    result = CliRunner().invoke(main, ['provision', '--config-fpath', str(config_fpath)])

    assert result.exit_code == 0
    assert seen['ran'] is True
    assert seen['config'].app_name == 'demo'
    assert seen['config'].vm_host_name == 'demo-vm'


def test_main_destroy(tmp_path, monkeypatch):
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
