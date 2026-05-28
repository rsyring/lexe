from subprocess import CompletedProcess
from unittest.mock import patch

from lexe.config import CLIOpts
from lexe.procs import ssh


class TestSsh:
    def test_quotes_remote_command(self, tmp_path):
        key_fpath = tmp_path / 'id-test'
        key_fpath.write_text('test')

        with patch(
            'lexe.procs.sub_run',
            return_value=CompletedProcess(('ssh',), 0, stdout='', stderr=''),
        ) as mock_sub_run:
            ssh(
                'demo-vm.exe.xyz',
                'printf',
                'hello world',
                '$HOME',
                opts=CLIOpts(ssh_ident_fpath=key_fpath),
            )

        mock_sub_run.assert_called_once_with(
            'ssh',
            args=(
                '-o',
                'StrictHostKeyChecking=accept-new',
                '-o',
                'IdentitiesOnly=yes',
                '-o',
                'IdentityAgent=none',
                '-i',
                key_fpath,
                'demo-vm.exe.xyz',
                "printf 'hello world' '$HOME'",
            ),
        )

    def test_requests_tty_when_asked(self):
        with patch(
            'lexe.procs.sub_run',
            return_value=CompletedProcess(('ssh',), 0, stdout='', stderr=''),
        ) as mock_sub_run:
            ssh(
                'demo-vm.exe.xyz',
                'bash',
                opts=CLIOpts(ssh_host_key_check=False, ssh_known_hosts_manage=False),
                tty=True,
            )

        assert mock_sub_run.call_args.kwargs['args'] == (
            '-t',
            '-o',
            'StrictHostKeyChecking=no',
            '-o',
            'UserKnownHostsFile=/dev/null',
            'demo-vm.exe.xyz',
            'bash',
        )
