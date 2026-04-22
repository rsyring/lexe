from pathlib import Path

import click

from lexe.config import CLIOpts, ConfigOpts, LexeConfig
from lexe.deploy import Deploy
from lexe.provision import Destroy, Provision
from lexe.status import Status


pass_config_opts = click.make_pass_decorator(ConfigOpts)


@click.group(context_settings={'auto_envvar_prefix': 'lexe'})
@click.option(
    '--config-fpath',
    type=click.Path(path_type=Path),
    default=Path('lexe.yaml'),
    show_envvar=True,
)
@click.option('-i', '--ssh-key', type=click.Path(path_type=Path, dir_okay=False, exists=True))
@click.option('--ssh-host-key-check/--no-ssh-host-key-check', default=True)
@click.option('--ssh-known-hosts-manage/--no-ssh-known-hosts-manage', default=True)
@click.pass_context
def main(
    ctx: click.Context,
    config_fpath: Path,
    ssh_key: Path | None,
    ssh_host_key_check: bool,
    ssh_known_hosts_manage: bool,
) -> None:
    if not ssh_host_key_check and ssh_known_hosts_manage:
        raise click.ClickException(
            '--ssh-known-hosts-manage requires --ssh-host-key-check',
        )

    ctx.obj = ConfigOpts(
        config=LexeConfig.find_lexe(config_fpath),
        opts=CLIOpts(
            ssh_ident_fpath=ssh_key,
            ssh_host_key_check=ssh_host_key_check,
            ssh_known_hosts_manage=ssh_known_hosts_manage,
        ),
    )


@main.command()
@pass_config_opts
def provision(config_opts: ConfigOpts) -> None:
    Provision(config_opts).run()


@main.command()
@pass_config_opts
def destroy(config_opts: ConfigOpts) -> None:
    Destroy(config_opts).run()


@main.command()
@click.option('--allow-dirty', is_flag=True)
@click.option('--restart-all', is_flag=True)
@pass_config_opts
def deploy(config_opts: ConfigOpts, allow_dirty: bool, restart_all: bool) -> None:
    Deploy(config_opts, allow_dirty=allow_dirty, restart_all=restart_all).run()


@main.command()
@pass_config_opts
def status(config_opts: ConfigOpts) -> None:
    Status(config_opts).run()
