from pathlib import Path
from urllib.request import urlopen

from click.testing import CliRunner
import pytest

from lexe.cli import main
from lexe.config import LexeConfig
from lexe.deploy import Deploy
from lexe.provision import Destroy, Provision


HELLO_APP_DPATH = Path(__file__).resolve().parents[2] / 'examples' / 'hello'
FLASK_APP_DPATH = Path(__file__).resolve().parents[2] / 'examples' / 'flask'


@pytest.mark.integration
@pytest.mark.usefixtures('provision')
class TestHello:
    @pytest.fixture(scope='class')
    def config(self):
        return LexeConfig.find_lexe(HELLO_APP_DPATH)

    @pytest.fixture
    def provision(self, config):
        try:
            Provision(config=config, app_dpath=HELLO_APP_DPATH).run()
            yield
        finally:
            Destroy(config=config).run()

    def test_deploy(self, config):
        Deploy(config=config, app_dpath=HELLO_APP_DPATH, allow_dirty=True).run()


@pytest.mark.integration
@pytest.mark.usefixtures('provision')
class TestFlask:
    @pytest.fixture(scope='class')
    def config(self):
        return LexeConfig.find_lexe(FLASK_APP_DPATH)

    @pytest.fixture
    def provision(self, config):
        try:
            Provision(config=config, app_dpath=FLASK_APP_DPATH).run()
            yield
        finally:
            Destroy(config=config).run()

    def test_deploy(self, config):
        Deploy(config=config, app_dpath=FLASK_APP_DPATH, allow_dirty=True).run()

        response = (
            urlopen(f'https://{config.vm_host_name}.exe.xyz:8000/', timeout=10).read().decode()
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
            ['status', '--config-fpath', str(FLASK_APP_DPATH / 'lexe.yaml')],
        )

        assert result.exit_code == 0
        assert 'VM reachable: yes' in result.output
        assert 'Compose project running: yes' in result.output
        assert 'Healthcheck: healthy (200)' in result.output
