# Copia a chave administrativa de produção para a área de transferência sem exibi-la.
# Requer a chave SSH da VM Recepia neste computador.
$ErrorActionPreference = 'Stop'
$sshKey = Join-Path $env:USERPROFILE '.ssh\recepia_oracle_ed25519'
if (-not (Test-Path -LiteralPath $sshKey)) { throw 'Chave SSH da VM não encontrada.' }
$adminKey = @(ssh -i $sshKey -o BatchMode=yes -o ConnectTimeout=10 ubuntu@132.226.243.173 "sudo sed -n 's/^ADMIN_API_KEY=//p' /home/ubuntu/recepia/.env")
if ($LASTEXITCODE -ne 0 -or -not $adminKey -or $adminKey.Count -ne 1 -or $adminKey[0].Length -lt 32) {
    throw 'Não foi possível obter a Admin Key de produção.'
}
Set-Clipboard -Value $adminKey[0]
$adminKey = $null
Write-Output 'Admin Key de produção copiada. Cole somente no campo Admin Key do painel.'
