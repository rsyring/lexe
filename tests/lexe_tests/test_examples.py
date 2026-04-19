from pathlib import Path

import pytest

from lexe.config import LexeConfig
from lexe.deploy import Deploy
from lexe.provision import Destroy, Provision


HELLO_APP_DPATH = Path(__file__).resolve().parents[2] / 'examples' / 'hello'


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
