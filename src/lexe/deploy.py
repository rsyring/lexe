from dataclasses import dataclass
from datetime import date
from pathlib import Path

import click

from lexe.config import LexeConfig
from lexe.procs import docker_ssh_command, exe_dev_test_key_fpath, sub_run, use_exe_dev_test_key


@dataclass
class Deploy:
    config: LexeConfig
    app_dpath: Path
    allow_dirty: bool = False
    wait_timeout_seconds: int = 90

    def run(self) -> None:
        self.ensure_required_files()
        dirty = self.is_dirty_worktree()
        self.ensure_dirty_allowed(dirty)
        image_ref = self.image_ref(dirty)
        compose_env = self.compose_env(image_ref)

        click.echo(f'Loaded lexe config for {self.config.app_name} ({self.config.vm_host_name}).')
        click.echo(f'Deploying {image_ref} to {self.remote_host}.')

        click.echo('Building image locally...')
        sub_run('docker', 'build', '-t', image_ref, '.', cwd=self.app_dpath)

        click.echo('Transferring image to remote VM...')
        sub_run(
            'docker',
            'pussh',
            *self.docker_pussh_args(),
            image_ref,
            self.remote_host,
            cwd=self.app_dpath,
            env=self.docker_pussh_env(),
        )

        self.run_hooks(
            'pre-start',
            self.config.hooks.pre_start,
            compose_env,
            abort_on_failure=True,
        )

        click.echo('Starting services on remote VM...')
        sub_run(
            'docker',
            *self.compose_args(),
            'up',
            '-d',
            '--wait',
            '--wait-timeout',
            str(self.wait_timeout_seconds),
            '--force-recreate',
            '--remove-orphans',
            cwd=self.app_dpath,
            env=compose_env,
        )

        self.run_hooks(
            'post-start',
            self.config.hooks.post_start,
            compose_env,
            abort_on_failure=False,
        )

        click.echo('Remote compose status:')
        result = sub_run(
            'docker',
            *self.compose_args(),
            'ps',
            capture=True,
            cwd=self.app_dpath,
            env=compose_env,
        )
        if result.stdout:
            click.echo(result.stdout.rstrip())

        click.echo('Deploy complete.')

    @property
    def remote_host(self) -> str:
        return f'{self.config.vm_host_name}.exe.xyz'

    def ensure_required_files(self) -> None:
        for name in ('Dockerfile', 'compose.yaml', 'compose.server.yaml'):
            if not (self.app_dpath / name).exists():
                raise click.ClickException(f'Missing required deploy file: {name}')

    def is_dirty_worktree(self) -> bool:
        result = sub_run('git', 'status', '--short', capture=True, cwd=self.app_dpath)
        return bool(result.stdout.strip())

    def ensure_dirty_allowed(self, dirty: bool) -> None:
        if dirty and not self.allow_dirty:
            raise click.ClickException(
                'Git working tree is dirty. Re-run with --allow-dirty to deploy uncommitted changes.',
            )

    def image_ref(self, dirty: bool) -> str:
        commit_sha = sub_run(
            'git',
            'rev-parse',
            'HEAD',
            capture=True,
            cwd=self.app_dpath,
        ).stdout.strip()
        release_tag = f'v{date.today().isoformat()}-{commit_sha[:7]}'
        if dirty:
            release_tag += '-dirty'
        return f'{self.config.app_name}:{release_tag}'

    def compose_args(self) -> tuple[str, ...]:
        return ('compose', '-f', 'compose.yaml', '-f', 'compose.server.yaml')

    def compose_env(self, image_ref: str) -> dict[str, str]:
        env = {
            'COMPOSE_PROJECT_NAME': self.config.app_name,
            'DOCKER_HOST': f'ssh://{self.remote_host}',
            'LEXE_IMAGE': image_ref,
        }
        if ssh_command := docker_ssh_command():
            env['DOCKER_SSH_COMMAND'] = ssh_command
        return env

    def docker_pussh_args(self) -> tuple[str | Path, ...]:
        key_fpath = exe_dev_test_key_fpath()
        if not use_exe_dev_test_key() or not key_fpath.exists():
            return ()
        return ('--ssh-key', key_fpath)

    def docker_pussh_env(self) -> dict[str, str] | None:
        key_fpath = exe_dev_test_key_fpath()
        if not use_exe_dev_test_key() or not key_fpath.exists():
            return None
        return {'SSH_STRICT_HOST_KEY_CHECKING': 'accept-new'}

    def run_hooks(
        self,
        phase: str,
        hooks,
        compose_env: dict[str, str],
        *,
        abort_on_failure: bool,
    ) -> None:
        for index, hook in enumerate(hooks, start=1):
            click.echo(
                f'Running {phase} hook {index} on service {hook.service}: {hook.display_command()}',
            )
            result = sub_run(
                'docker',
                *self.compose_args(),
                'run',
                '--rm',
                '--no-deps',
                '--env',
                f'LEXE_HOOK_NAME={phase}',
                *hook.compose_run_args(),
                cwd=self.app_dpath,
                env=compose_env,
                capture=True,
                check=abort_on_failure,
            )
            if result.returncode != 0:
                click.echo(
                    f'{phase.capitalize()} hook {index} failed on service '
                    f'{hook.service} with exit code {result.returncode}.',
                )
                self.echo_hook_output(result.stdout, label='stdout')
                self.echo_hook_output(result.stderr, label='stderr')

    def echo_hook_output(self, text: str, *, label: str) -> None:
        stripped = text.strip()
        if stripped:
            click.echo(f'Hook {label}: {stripped}')
