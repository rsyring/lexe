from lexe.config import LexeConfig


def test_provision_config_from_fpath(tmp_path):
    config_fpath = tmp_path / 'lexe.yaml'
    config_fpath.write_text(
        'app-name: demo\nvm-host-name: demo-vm\npublic-service: web\n',
    )

    config = LexeConfig.from_yaml(config_fpath)

    assert config.app_name == 'demo'
    assert config.vm_host_name == 'demo-vm'
    assert config.public_service == 'web'


def test_provision_config_find_lexe_from_directory(tmp_path):
    app_dpath = tmp_path / 'app'
    nested_dpath = app_dpath / 'deploy'
    nested_dpath.mkdir(parents=True)
    (app_dpath / 'lexe.yaml').write_text('app-name: demo\nvm-host-name: demo-vm\n')

    config = LexeConfig.find_lexe(nested_dpath)

    assert config.app_name == 'demo'
    assert config.vm_host_name == 'demo-vm'
