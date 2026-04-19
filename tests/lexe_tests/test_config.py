from lexe.config import LexeConfig


class TestLexeConfig:
    def test_from_yaml(self, tmp_path):
        config_fpath = tmp_path / 'lexe.yaml'
        config_fpath.write_text(
            'app-name: demo\nvm-host-name: demo-vm\npublic-service: web\n',
        )

        config = LexeConfig.from_yaml(config_fpath)

        assert config.app_name == 'demo'
        assert config.vm_host_name == 'demo-vm'
        assert config.public_service == 'web'

    def test_from_yaml_parses_healthcheck_and_hooks(self, tmp_path):
        config_fpath = tmp_path / 'lexe.yaml'
        config_fpath.write_text(
            '\n'.join(
                [
                    'app-name: demo',
                    'vm-host-name: demo-vm',
                    'healthcheck-url: https://demo.exe.xyz/health',
                    'hooks:',
                    '  pre-start: echo pre',
                    '  post-start:',
                    '    - python',
                    '    - -c',
                    "    - print('post')",
                    '',
                ],
            ),
        )

        config = LexeConfig.from_yaml(config_fpath)

        assert config.healthcheck_url == 'https://demo.exe.xyz/health'
        assert len(config.hooks.pre_start) == 1
        assert config.hooks.pre_start[0].service == 'web'
        assert config.hooks.pre_start[0].command == 'echo pre'
        assert len(config.hooks.post_start) == 1
        assert config.hooks.post_start[0].command == ('python', '-c', "print('post')")

    def test_find_lexe(self, tmp_path):
        app_dpath = tmp_path / 'app'
        nested_dpath = app_dpath / 'deploy'
        nested_dpath.mkdir(parents=True)
        (app_dpath / 'lexe.yaml').write_text('app-name: demo\nvm-host-name: demo-vm\n')

        config = LexeConfig.find_lexe(nested_dpath)

        assert config.app_name == 'demo'
        assert config.vm_host_name == 'demo-vm'
