from pathlib import Path

import pytest

from lexe.config import CLIOpts


TEST_EXE_DEV_SSH_KEY_FPATH = (
    Path(__file__).resolve().parents[1] / 'ssh-keys' / 'id_lexe_exe_dev_tests'
)


@pytest.fixture(scope='class')
def integration_cli_opts() -> CLIOpts:
    return CLIOpts(
        ssh_ident_fpath=TEST_EXE_DEV_SSH_KEY_FPATH,
        ssh_host_key_check=False,
        ssh_known_hosts_manage=False,
    )
