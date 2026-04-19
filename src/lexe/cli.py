from pathlib import Path

import click

from lexe.config import LexeConfig, find_lexe_fpath
from lexe.deploy import Deploy
from lexe.provision import Destroy, Provision


@click.group()
def main() -> None:
    pass


@main.command()
@click.option(
    '--config-fpath',
    type=click.Path(path_type=Path),
    default=Path('lexe.yaml'),
)
def provision(config_fpath: Path) -> None:
    config_fpath = find_lexe_fpath(config_fpath)
    config = LexeConfig.from_yaml(config_fpath)
    Provision(config=config, app_dpath=config_fpath.parent).run()


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
