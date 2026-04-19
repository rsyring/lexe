from click.testing import CliRunner

from lexe.cli import main


def test_main_provision(tmp_path):
    config_fpath = tmp_path / 'lexe.yaml'
    config_fpath.write_text('app-name: demo\nvm-host-name: demo-vm\n')

    result = CliRunner().invoke(main, ['provision', '--config-fpath', str(config_fpath)])

    assert result.exit_code == 0
    assert 'Loaded lexe config for demo (demo-vm).' in result.output
