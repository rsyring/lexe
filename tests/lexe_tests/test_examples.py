from pathlib import Path
from urllib.request import urlopen

import pytest

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
