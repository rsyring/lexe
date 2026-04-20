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
@click.pass_context
def main(ctx: click.Context, config_fpath: Path, ssh_key: Path) -> None:
    ctx.obj = ConfigOpts(
        LexeConfig.find_lexe(config_fpath),
        CLIOpts(ssh_key=ssh_key),
    )


@main.command()
@pass_config_opts
def provision(config_opts: ConfigOpts) -> None:
    Provision(ConfigOpts).run()


@main.command()
@click.option(
    '--config-fpath',
    type=click.Path(path_type=Path),
    default=Path('lexe.yaml'),
)
def destroy(config_fpath: Path) -> None:
    config = LexeConfig.find_lexe(config_fpath)
    Destroy(config=config).run()


@main.command()
@click.option(
    '--config-fpath',
    type=click.Path(path_type=Path),
    default=Path('lexe.yaml'),
)
@click.option('--allow-dirty', is_flag=True)
def deploy(config_fpath: Path, allow_dirty: bool) -> None:
    config_fpath = find_lexe_fpath(config_fpath)
    config = LexeConfig.from_yaml(config_fpath)
    Deploy(config=config, app_dpath=config_fpath.parent, allow_dirty=allow_dirty).run()


@main.command()
@click.option(
    '--config-fpath',
    type=click.Path(path_type=Path),
    default=Path('lexe.yaml'),
)
def status(config_fpath: Path) -> None:
    config_fpath = find_lexe_fpath(config_fpath)
    config = LexeConfig.from_yaml(config_fpath)
    Status(config=config, app_dpath=config_fpath.parent).run()
