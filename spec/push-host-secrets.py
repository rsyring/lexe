#!/usr/bin/env python3
"""
# [MISE] description="Copy secrets from 1P to host"
"""

from dataclasses import dataclass
import json

import click
from furl import furl

from kilo.libs import sub_run


@dataclass
class HostConfig:
    hostname: str
    op_acct: str
    ssh_key_ref: str
    op_svc_token: str

    @property
    def private_key_ref(self):
        return f'{self.ssh_key_ref}/private key?ssh-format=openssh'

    @property
    def key_type_ref(self):
        return f'{self.ssh_key_ref}/key type'


# Define hostname to 1Password secret reference mapping
HOST_CONFIGS = (
    HostConfig(
        hostname='syring-checks.exe.xyz',
        op_acct='my',
        ssh_key_ref='op://app-syring-checks/syring-checks-deploy-key',
        op_svc_token='op://app-syring-checks/Syring Checks 1Pass Auth Token/credential',
    ),
    HostConfig(
        hostname='blaze-ops.exe.xyz',
        op_acct='my',
        ssh_key_ref='op://app-blaze-ops/blaze-ops-deploy-key',
        op_svc_token='op://app-blaze-ops/blaze-ops-1pass-auth-token/credential',
    ),
)

HOST_CONFIGS = {hc.hostname: hc for hc in HOST_CONFIGS}


@dataclass(frozen=True)
class OpSecretRef:
    account: str | None
    vault: str
    item: str
    field: str


def parse_op_secret_ref(op_ref: str) -> OpSecretRef:
    parts = furl(op_ref)
    segments = parts.path.segments
    if parts.scheme != 'op' or len(segments) not in (2, 3):
        raise click.ClickException('Use a 1Password ref like op://VAULT/ITEM/FIELD')

    if len(segments) == 2:
        return OpSecretRef(account=None, vault=parts.host, item=segments[0], field=segments[1])

    return OpSecretRef(account=parts.host, vault=segments[0], item=segments[1], field=segments[2])


def service_account_vault_name(hostname: str) -> str:
    host = furl(f'https://{hostname}').host
    host_parts = host.split('.')
    if len(host_parts) < 3 or host_parts[-2:] != ['exe', 'xyz']:
        raise click.ClickException(f'Expected an exe.xyz hostname, got: {hostname}')
    return f'app-{"-".join(host_parts[:-2])}'


def op_item_args(acct: str, op_ref: OpSecretRef) -> tuple[str, ...]:
    return ('--account', acct, '--vault', op_ref.vault, op_ref.item)


def op_missing_item_msg(op_ref: OpSecretRef) -> str:
    return f'"{op_ref.item}" isn\'t an item in the "{op_ref.vault}" vault.'


def op_item_exists(acct: str, op_ref: OpSecretRef) -> bool:
    result = sub_run(
        'op',
        'item',
        'get',
        *op_item_args(acct, op_ref),
        '--format',
        'json',
        capture=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    if op_missing_item_msg(op_ref) in result.stderr:
        return False
    raise click.ClickException(result.stderr.strip() or result.stdout.strip())


def op_vault_exists(acct: str, vault_name: str) -> bool:
    result = sub_run('op', 'vault', 'list', '--account', acct, '--format', 'json', capture=True)
    return any(vault['name'] == vault_name for vault in json.loads(result.stdout))


def ensure_op_vault(acct: str, vault_name: str) -> None:
    if not op_vault_exists(acct, vault_name):
        sub_run('op', 'vault', 'create', vault_name, '--account', acct)


def create_service_account_token(acct: str, service_account_name: str, vault_name: str) -> str:
    result = sub_run(
        'op',
        'service-account',
        'create',
        service_account_name,
        '--account',
        acct,
        '--vault',
        f'{vault_name}:read_items,write_items',
        '--raw',
        capture=True,
    )
    return result.stdout.strip()


def create_service_token_item(acct: str, hostname: str, op_ref: OpSecretRef, token: str) -> None:
    result = sub_run('op', 'item', 'template', 'get', 'API Credential', capture=True)
    item = json.loads(result.stdout)
    item['title'] = op_ref.item
    for field in item['fields']:
        if field['id'] == op_ref.field:
            field['value'] = token
        elif field['id'] == 'hostname':
            field['value'] = hostname

    sub_run(
        'op',
        'item',
        'create',
        '--account',
        acct,
        '--vault',
        op_ref.vault,
        '-',
        input=json.dumps(item),
        text=True,
    )


def ensure_service_token(acct: str, hostname: str, op_ref_str: str) -> str:
    op_ref = parse_op_secret_ref(op_ref_str)
    acct = op_ref.account or acct
    vault_name = service_account_vault_name(hostname)
    if op_ref.vault != vault_name:
        raise click.ClickException(
            f'op_svc_token vault must be {vault_name!r}, got {op_ref.vault!r}',
        )

    if op_item_exists(acct, op_ref):
        return op_read(acct, op_ref_str)

    ensure_op_vault(acct, vault_name)
    svc_token = create_service_account_token(acct, vault_name, vault_name)
    create_service_token_item(acct, hostname, op_ref, svc_token)
    return svc_token


def op_read(acct: str, ref: str) -> str:
    """
    Retrieve secret from 1Password using the CLI.
    """
    result = sub_run('op', 'read', '--account', acct, ref, capture=True)
    return result.stdout


def get_key_filename(key_type: str) -> str:
    """
    Determine SSH key filename based on key type from 1Password.

    Args:
        key_type: Key type string from 1Password (e.g., 'ed25519', 'rsa', 'ecdsa')

    Returns:
        Appropriate filename for the key type
    """
    key_type_lower = key_type.lower()

    if 'ed25519' in key_type_lower:
        return 'id_ed25519'
    elif 'rsa' in key_type_lower:
        return 'id_rsa'
    elif 'ecdsa' in key_type_lower:
        return 'id_ecdsa'
    elif 'dsa' in key_type_lower:
        return 'id_dsa'
    else:
        # Fallback to generic name
        return 'id_rsa'


def deploy_ssh_key(hostname: str, key_filename: str, private_key: str) -> None:
    """
    Deploy SSH private key to remote host.

    Args:
        hostname: Target hostname
        key_filename: SSH key filename to use
        private_key: SSH private key content
    """
    ssh_commands = (
        'mkdir -p ~/.ssh && '
        'chmod 700 ~/.ssh && '
        f'cat > ~/.ssh/{key_filename} && '
        f'chmod 600 ~/.ssh/{key_filename}'
    )

    # Use ssh with stdin to avoid writing key to disk
    sub_run(
        'ssh',
        hostname,
        ssh_commands,
        input=private_key,
        text=True,
    )


def deploy_svc_token(hostname: str, svc_token: str) -> None:
    """
    Deploy 1Password service token to remote host.

    Args:
        hostname: Target hostname
        svc_token: 1Password service token content
    """
    ssh_commands = (
        'mkdir -p ~/.config && '
        'cat > ~/.config/1pass-svc-token.txt && '
        'chmod 600 ~/.config/1pass-svc-token.txt'
    )

    # Use ssh with stdin to avoid writing token to disk
    sub_run(
        'ssh',
        hostname,
        ssh_commands,
        input=svc_token,
        text=True,
    )


@click.command()
@click.argument(
    'hostname',
    type=click.Choice(HOST_CONFIGS.keys()),
)
def main(hostname: str) -> None:
    """
    Deploy SSH private key from 1Password to a remote host.

    The private key is retrieved from 1Password and deployed to the remote host
    without ever being written to local disk.

    HOSTNAME: The target host to deploy the SSH key to.
    """
    config = HOST_CONFIGS[hostname]

    click.echo(f'Deploying SSH key to: {config.hostname}')
    click.echo(f'1Password reference: {config.ssh_key_ref}')

    # Retrieve key type and private key from 1Password
    key_type = op_read(config.op_acct, config.key_type_ref)
    private_key = op_read(config.op_acct, config.private_key_ref)

    # Determine filename and deploy SSH key
    key_filename = get_key_filename(key_type)
    deploy_ssh_key(config.hostname, key_filename, private_key)

    # Retrieve and deploy 1Password service token
    svc_token = ensure_service_token(config.op_acct, config.hostname, config.op_svc_token)
    deploy_svc_token(config.hostname, svc_token)

    click.echo(f'✓ Secrets successfully deployed to {config.hostname}')


if __name__ == '__main__':
    main()
