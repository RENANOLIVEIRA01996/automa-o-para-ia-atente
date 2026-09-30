param([switch]$Generate)

# Define a senha do Admin Master na VM usando somente o hash PBKDF2.
# Sem -Generate, solicita uma senha nova no próprio terminal (nunca pelo chat).
$ErrorActionPreference = 'Stop'
$sshKey = Join-Path $env:USERPROFILE '.ssh\recepia_oracle_ed25519'
if (-not (Test-Path -LiteralPath $sshKey)) { throw 'Chave SSH da VM não encontrada.' }

if ($Generate) {
    $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
    $passwordBytes = New-Object byte[] 30
    try { $rng.GetBytes($passwordBytes) }
    finally { $rng.Dispose() }
    $password = [Convert]::ToBase64String($passwordBytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
} else {
    $secure = Read-Host 'Digite uma senha NOVA para o Admin Master (mínimo 14 caracteres)' -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    if ($password.Length -lt 14) { throw 'Use pelo menos 14 caracteres e não reutilize uma senha enviada em mensagens.' }
}

$rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
$salt = New-Object byte[] 16
try { $rng.GetBytes($salt) }
finally { $rng.Dispose() }
$kdf = New-Object System.Security.Cryptography.Rfc2898DeriveBytes($password, $salt, 600000, [System.Security.Cryptography.HashAlgorithmName]::SHA256)
try { $digest = $kdf.GetBytes(32) }
finally { $kdf.Dispose() }
$encode = { param([byte[]]$bytes) [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_') }
$hashText = 'pbkdf2_sha256$600000$' + (& $encode $salt) + '$' + (& $encode $digest)
$hashText | ssh -i $sshKey -o BatchMode=yes -o ConnectTimeout=10 ubuntu@132.226.243.173 'umask 077; cat > /home/ubuntu/recepia/.admin-password-hash.pending'
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível transferir o hash da senha.' }

$remoteScript = @'
from pathlib import Path
import os
p=Path('/home/ubuntu/recepia/.env')
h=Path('/home/ubuntu/recepia/.admin-password-hash.pending')
value=h.read_text(encoding='ascii').strip()
if not value.startswith('pbkdf2_sha256$600000$'):
    raise SystemExit('Hash inválido')
lines=p.read_text(encoding='utf-8').splitlines(keepends=True)
lines=[line for line in lines if not line.startswith('ADMIN_PANEL_PASSWORD_HASH=')]
if lines and not lines[-1].endswith('\n'):
    lines[-1] += '\n'
lines.append("ADMIN_PANEL_PASSWORD_HASH='"+value+"'\n")
tmp=p.with_name('.env.password-pending')
tmp.write_text(''.join(lines),encoding='utf-8')
os.chmod(tmp,0o600)
os.replace(tmp,p)
h.unlink()
print('Hash da senha atualizado na VM')
'@
$remoteScript | ssh -i $sshKey -o BatchMode=yes ubuntu@132.226.243.173 'sudo python3 -'
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível atualizar a senha na VM.' }
ssh -i $sshKey -o BatchMode=yes ubuntu@132.226.243.173 'cd /home/ubuntu/recepia && sudo docker compose -f docker-compose.production.api.yml up -d --no-build --force-recreate api worker' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Senha salva, mas a API não reiniciou. Verifique a VM.' }

if ($Generate) {
    Set-Clipboard -Value $password
    Write-Output 'Senha forte gerada e copiada para a área de transferência. Cole no Admin Master.'
} else {
    Write-Output 'Senha do Admin Master atualizada. Entre com a senha que você digitou no terminal.'
}
$password = $null
