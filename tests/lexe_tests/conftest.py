import os

import pytest


@pytest.fixture(autouse=True)
def enable_exe_dev_test_key_for_integration_tests(request):
    if 'integration' not in request.keywords:
        yield
        return

    original_value = os.environ.get('LEXE_USE_EXE_DEV_TEST_KEY')
    original_strict_host_key_checking = os.environ.get('SSH_STRICT_HOST_KEY_CHECKING')
    os.environ['LEXE_USE_EXE_DEV_TEST_KEY'] = '1'
    os.environ['SSH_STRICT_HOST_KEY_CHECKING'] = 'accept-new'

    try:
        yield
    finally:
        if original_value is None:
            os.environ.pop('LEXE_USE_EXE_DEV_TEST_KEY', None)
        else:
            os.environ['LEXE_USE_EXE_DEV_TEST_KEY'] = original_value
        if original_strict_host_key_checking is None:
            os.environ.pop('SSH_STRICT_HOST_KEY_CHECKING', None)
        else:
            os.environ['SSH_STRICT_HOST_KEY_CHECKING'] = original_strict_host_key_checking
