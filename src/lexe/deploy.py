from dataclasses import dataclass
from datetime import date
from pathlib import Path

import click

from lexe.config import LexeConfig
from lexe.procs import sub_run


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

        click.echo(f'Loaded lexe config for {self.config.app_name} ({self.config.vm_host_name}).')
        click.echo(f'Deploying {image_ref} to {self.remote_host}.')

        click.echo('Building image locally...')
        sub_run('docker', 'build', '-t', image_ref, '.', cwd=self.app_dpath)

        click.echo('Transferring image to remote VM...')
        sub_run('docker', 'pussh', image_ref, self.remote_host, cwd=self.app_dpath)

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
            env=self.compose_env(image_ref),
        )

        click.echo('Remote compose status:')
        result = sub_run(
            'docker',
            *self.compose_args(),
            'ps',
            capture=True,
            cwd=self.app_dpath,
            env=self.compose_env(image_ref),
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
            'git', 'rev-parse', 'HEAD', capture=True, cwd=self.app_dpath
        ).stdout.strip()
        release_tag = f'v{date.today().isoformat()}-{commit_sha[:7]}'
        if dirty:
            release_tag += '-dirty'
        return f'{self.config.app_name}:{release_tag}'

    def compose_args(self) -> tuple[str, ...]:
        return ('compose', '-f', 'compose.yaml', '-f', 'compose.server.yaml')

    def compose_env(self, image_ref: str) -> dict[str, str]:
        return {
            'COMPOSE_PROJECT_NAME': self.config.app_name,
            'DOCKER_HOST': f'ssh://{self.remote_host}',
            'LEXE_IMAGE': image_ref,
        }
