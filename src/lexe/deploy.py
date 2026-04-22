from dataclasses import dataclass
from datetime import date
from pathlib import Path

import click

from lexe.config import CLIOpts, ConfigOpts, HookCommand, LexeConfig
from lexe.procs import (
    docker_client_env,
    docker_host_url,
    docker_pussh_args,
    docker_pussh_env,
    sub_run,
)


@dataclass
class Deploy:
    config_opts: ConfigOpts
    allow_dirty: bool = False
    restart_all: bool = False
    wait_timeout_seconds: int = 90

    @property
    def config(self) -> LexeConfig:
        return self.config_opts.config

    @property
    def opts(self) -> CLIOpts:
        return self.config_opts.opts

    @property
    def app_dpath(self) -> Path:
        return self.config.project.path

    @property
    def app_name(self) -> str:
        return self.config.project.name

    @property
    def vm_host_name(self) -> str:
        return self.config.project.vm_host

    def run(self) -> None:
        self.ensure_required_files()
        dirty = self.is_dirty_worktree()
        self.ensure_dirty_allowed(dirty)
        contingent_service_names = self.contingent_service_names()
        deploy_service_names = self.deploy_service_names()
        image_ref = self.image_ref(dirty)

        with (
            docker_host_url(self.remote_host, self.opts) as docker_host,
            docker_client_env(self.remote_host, self.opts) as docker_env,
        ):
            compose_env = self.compose_env(image_ref, docker_host) | docker_env

            click.echo(f'Loaded lexe config for {self.app_name} ({self.vm_host_name}).')
            click.echo(f'Deploying {image_ref} to {self.remote_host}.')

            click.echo('Building image locally...')
            sub_run('docker', 'build', '-t', image_ref, '.', cwd=self.app_dpath)

            click.echo('Transferring image to remote VM...')
            sub_run(
                'docker',
                'pussh',
                *docker_pussh_args(self.opts),
                image_ref,
                self.remote_host,
                cwd=self.app_dpath,
                env=(docker_pussh_env(self.opts) or {}) | docker_env,
            )

            if contingent_service_names:
                click.echo('Starting contingent services on remote VM...')
                self.start_service_group(
                    contingent_service_names,
                    compose_env,
                    recreate=self.restart_all,
                )

            self.run_hooks(
                'pre-start',
                self.service_hooks('start_pre', deploy_service_names),
                compose_env,
                abort_on_failure=True,
            )

            click.echo('Starting services on remote VM...')
            self.start_service_group(deploy_service_names, compose_env, recreate=True)

            self.run_hooks(
                'post-start',
                self.service_hooks('start_post', deploy_service_names),
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
        return f'{self.vm_host_name}.exe.xyz'

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
                'Git working tree is dirty. Re-run with --allow-dirty to deploy '
                'uncommitted changes.',
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
        return f'{self.app_name}:{release_tag}'

    def compose_args(self) -> tuple[str, ...]:
        return ('compose', '-f', 'compose.yaml', '-f', 'compose.server.yaml')

    def compose_env(self, image_ref: str, docker_host: str) -> dict[str, str]:
        env = {
            'COMPOSE_PROJECT_NAME': self.app_name,
            'DOCKER_HOST': docker_host,
            'LEXE_IMAGE': image_ref,
        }
        return env

    def deploy_service_names(self) -> tuple[str, ...]:
        service_names = tuple(
            service_name
            for service_name, service in self.config.services.items()
            if service.deploy == 'always'
        )
        if service_names:
            return service_names

        raise click.ClickException(
            'No services are configured for direct deploy. Mark at least one service with '
            'deploy: always.',
        )

    def contingent_service_names(self) -> tuple[str, ...]:
        return tuple(
            service_name
            for service_name, service in self.config.services.items()
            if service.deploy == 'contingent'
        )

    def start_service_group(
        self,
        service_names: tuple[str, ...],
        compose_env: dict[str, str],
        *,
        recreate: bool,
    ) -> None:
        recreate_arg = '--force-recreate' if recreate else '--no-recreate'
        sub_run(
            'docker',
            *self.compose_args(),
            'up',
            '-d',
            '--wait',
            '--wait-timeout',
            str(self.wait_timeout_seconds),
            recreate_arg,
            '--remove-orphans',
            *service_names,
            cwd=self.app_dpath,
            env=compose_env,
        )

    def service_hooks(
        self,
        attr_name: str,
        service_names: tuple[str, ...],
    ) -> list[tuple[str, HookCommand]]:
        return [
            (service_name, hook_command)
            for service_name in service_names
            for hook_command in getattr(self.config.services[service_name].hooks, attr_name)
        ]

    def run_hooks(
        self,
        phase: str,
        hooks: list[tuple[str, HookCommand]],
        compose_env: dict[str, str],
        *,
        abort_on_failure: bool,
    ) -> None:
        for index, (service_name, hook_command) in enumerate(hooks, start=1):
            click.echo(
                f'Running {phase} hook {index} on service '
                f'{service_name}: {self.display_command(hook_command)}',
            )
            result = sub_run(
                'docker',
                *self.compose_args(),
                'run',
                '--rm',
                '--env',
                f'LEXE_HOOK_NAME={phase}',
                *self.compose_run_args(service_name, hook_command),
                cwd=self.app_dpath,
                env=compose_env,
                capture=True,
                check=abort_on_failure,
            )
            if result.returncode != 0:
                click.echo(
                    f'{phase.capitalize()} hook {index} failed on service '
                    f'{service_name} with exit code {result.returncode}.',
                )
                self.echo_hook_output(result.stdout, label='stdout')
                self.echo_hook_output(result.stderr, label='stderr')

    def compose_run_args(self, service_name: str, hook_command: HookCommand) -> tuple[str, ...]:
        if isinstance(hook_command, str):
            return ('--entrypoint', 'sh', service_name, '-lc', hook_command)

        assert hook_command
        return ('--entrypoint', hook_command[0], service_name, *hook_command[1:])

    def display_command(self, hook_command: HookCommand) -> str:
        if isinstance(hook_command, str):
            return hook_command

        return ' '.join(hook_command)

    def echo_hook_output(self, text: str, *, label: str) -> None:
        stripped = text.strip()
        if stripped:
            click.echo(f'Hook {label}: {stripped}')
