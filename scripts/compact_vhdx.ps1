# Stop Docker Desktop, compact its data vhdx with diskpart, restart.
# Run this script normally; it elevates only the diskpart call (one UAC prompt).
$ErrorActionPreference = 'Stop'
$vhdx = 'C:\Users\DELL\AppData\Local\Docker\wsl\disk\docker_data.vhdx'
$dockerExe = 'C:\Users\DELL\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe'
$dockerCli = 'C:\Users\DELL\AppData\Local\Programs\DockerDesktop\DockerCli.exe'

Write-Host 'Stopping Docker Desktop...'
& $dockerCli -Shutdown | Out-Null
for ($i = 0; $i -lt 30; $i++) {
    $running = Get-Process 'Docker Desktop', 'com.docker.backend' -ErrorAction SilentlyContinue
    if (-not $running) { break }
    Start-Sleep -Seconds 2
}
if (Get-Process 'com.docker.backend' -ErrorAction SilentlyContinue) {
    throw 'Docker backend is still running; aborting before touching the vhdx.'
}
Start-Sleep -Seconds 5

$before = (Get-Item $vhdx).Length / 1GB
Write-Host ('vhdx before: {0:N2} GB' -f $before)

$script = Join-Path $env:TEMP 'compact_docker_data.txt'
@"
select vdisk file="$vhdx"
attach vdisk readonly
compact vdisk
detach vdisk
exit
"@ | Set-Content -Path $script -Encoding ASCII

Write-Host 'Running diskpart (UAC prompt)...'
$p = Start-Process diskpart -ArgumentList "/s `"$script`"" -Verb RunAs -Wait -PassThru
Write-Host ('diskpart exit code: {0}' -f $p.ExitCode)

$after = (Get-Item $vhdx).Length / 1GB
Write-Host ('vhdx after: {0:N2} GB (reclaimed {1:N2} GB)' -f $after, ($before - $after))

Write-Host 'Restarting Docker Desktop...'
Start-Process $dockerExe
