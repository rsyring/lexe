from pathlib import Path
from urllib.request import urlopen

from click.testing import CliRunner
import pytest

from lexe.cli import main
from lexe.config import CLIOpts, ConfigOpts, LexeConfig
from lexe.deploy import Deploy
from lexe.provision import Destroy, Provision


HELLO_APP_DPATH = Path(__file__).resolve().parents[2] / 'examples' / 'hello'
FLASK_APP_DPATH = Path(__file__).resolve().parents[2] / 'examples' / 'flask'


def config_opts(app_dpath: Path, opts: CLIOpts) -> ConfigOpts:
    return ConfigOpts(config=LexeConfig.find_lexe(app_dpath), opts=opts)


@pytest.mark.integration
@pytest.mark.usefixtures('provision')
class TestHello:
    @pytest.fixture(scope='class')
    def config_opts_(self, integration_cli_opts):
        return config_opts(HELLO_APP_DPATH, integration_cli_opts)

    @pytest.fixture
    def provision(self, config_opts_):
        try:
            Provision(config_opts_).run()
            yield
        finally:
            Destroy(config_opts_).run()

    def test_deploy(self, config_opts_):
        Deploy(config_opts_, allow_dirty=True).run()


@pytest.mark.integration
@pytest.mark.usefixtures('provision')
class TestFlask:
    @pytest.fixture(scope='class')
    def config_opts_(self, integration_cli_opts):
        return config_opts(FLASK_APP_DPATH, integration_cli_opts)

    @pytest.fixture
    def provision(self, config_opts_):
        try:
            Provision(config_opts_).run()
            yield
        finally:
            Destroy(config_opts_).run()

    def test_deploy(self, config_opts_):
        Deploy(config_opts_, allow_dirty=True).run()

        config = config_opts_.config
        response = (
            urlopen(f'https://{config.project.vm_host}.exe.xyz:8000/', timeout=10).read().decode()
        )
        assert 'Hello, World!' in response
        assert '<pre>' in response
        assert 'pre-start' in response
        assert 'app.py startup' in response
        assert 'post-start' in response
        assert (
            response.index('pre-start')
            < response.index('app.py startup')
            < response.index('post-start')
        )

        result = CliRunner().invoke(
            main,
            [
                '--config-fpath',
                str(FLASK_APP_DPATH / 'lexe.yaml'),
                '--ssh-key',
                str(config_opts_.opts.ssh_ident_fpath),
                '--no-ssh-host-key-check',
                '--no-ssh-known-hosts-manage',
                'status',
            ],
        )

        assert result.exit_code == 0
        assert 'VM reachable: yes' in result.output
        assert 'Compose project running: yes' in result.output
        assert 'Healthcheck: healthy (200)' in result.output
