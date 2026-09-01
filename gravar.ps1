# Grava amostras de voz para a bancada. Sem ErrorActionPreference=Stop:
# o ffmpeg retorna codigo de erro ao listar dispositivos, e isso e normal.
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$destino = Join-Path $raiz "amostras"
if (-not (Test-Path $destino)) { New-Item -ItemType Directory -Force $destino | Out-Null }

# --- localizar ffmpeg ---
$ff = $null
$cands = @(
  "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe",
  "$env:LOCALAPPDATA\Microsoft\WinGet\Links\ffmpeg.exe"
)
foreach ($c in $cands) { if (Test-Path $c) { $ff = $c; break } }
if (-not $ff) {
  $ff = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter ffmpeg.exe -EA SilentlyContinue | Select-Object -First 1).FullName
}
if (-not $ff) { Write-Host "ffmpeg nao encontrado." -ForegroundColor Red; Read-Host "Enter para sair"; exit 1 }

# --- listar microfones ---
# O ffmpeg escreve a lista no stderr. No PowerShell 5.1, "2>&1" embrulha cada
# linha num objeto de erro e a captura quebra -- por isso o desvio para arquivo.
$tmp = Join-Path $env:TEMP ("ffdev_" + [guid]::NewGuid().ToString("N") + ".txt")
Start-Process -FilePath $ff -ArgumentList '-hide_banner','-list_devices','true','-f','dshow','-i','dummy' -NoNewWindow -Wait -RedirectStandardError $tmp
$saida = ""
if (Test-Path $tmp) { $saida = Get-Content $tmp -Raw -EA SilentlyContinue; Remove-Item $tmp -Force -EA SilentlyContinue }

$mics = @()
foreach ($linha in ($saida -split "`r?`n")) {
  if ($linha -match '"([^"]+)"\s*\(audio\)') { $mics += $matches[1] }
}

Write-Host ""
Write-Host "  MICROFONES DISPONIVEIS" -ForegroundColor Cyan
Write-Host "  ----------------------"
if ($mics.Count -eq 0) {
  Write-Host "  nenhum microfone encontrado." -ForegroundColor Red
  Write-Host "  saida crua do ffmpeg, para diagnostico:" -ForegroundColor DarkGray
  Write-Host $saida -ForegroundColor DarkGray
  Read-Host "  Enter para sair"; exit 1
}
for ($i = 0; $i -lt $mics.Count; $i++) { Write-Host ("   [{0}] {1}" -f ($i+1), $mics[$i]) }
Write-Host ""

# --- lembrar a escolha entre execucoes ---
$memo = Join-Path $raiz ".microfone"
$padrao = 1
if (Test-Path $memo) {
  $salvo = (Get-Content $memo -Raw -EA SilentlyContinue)
  if ($salvo) {
    $salvo = $salvo.Trim()
    $idx = [array]::IndexOf($mics, $salvo)
    if ($idx -ge 0) { $padrao = $idx + 1 }
  }
}
$esc = Read-Host ("  Qual microfone? [Enter = {0}]" -f $padrao)
if ([string]::IsNullOrWhiteSpace($esc)) { $esc = $padrao }
$iesc = 0
if (-not [int]::TryParse($esc, [ref]$iesc)) { $iesc = $padrao }
if ($iesc -lt 1 -or $iesc -gt $mics.Count) { $iesc = $padrao }
$mic = $mics[$iesc - 1]
Set-Content -Path $memo -Value $mic -Encoding utf8
Write-Host ("  usando: {0}" -f $mic) -ForegroundColor Green

# --- qual amostra ---
Write-Host ""
$n = Read-Host "  Numero da amostra (1, 2 ou 3)"
if ($n -notmatch '^[123]$') { Write-Host "  precisa ser 1, 2 ou 3." -ForegroundColor Red; Read-Host "  Enter para sair"; exit 1 }

# --- mostrar o roteiro na tela ---
$roteiro = Join-Path $destino ("leitura-0{0}.txt" -f $n)
if (Test-Path $roteiro) {
  Write-Host ""
  Write-Host "  ------------------------------------------------------------" -ForegroundColor DarkCyan
  if ($n -eq "1") {
    Write-Host "   LEIA ISTO EM VOZ ALTA (como se estivesse falando):" -ForegroundColor Cyan
  } else {
    Write-Host "   O QUE FAZER NESTA AMOSTRA:" -ForegroundColor Cyan
  }
  Write-Host "  ------------------------------------------------------------" -ForegroundColor DarkCyan
  Write-Host ""
  Get-Content $roteiro -Encoding UTF8 | ForEach-Object { Write-Host ("   " + $_) }
  Write-Host ""
  Write-Host "  ------------------------------------------------------------" -ForegroundColor DarkCyan
  Read-Host "  leia com calma, e aperte Enter quando estiver pronto para gravar"
}

$arquivo = Join-Path $destino ("amostra-{0}.wav" -f $n)
if (Test-Path $arquivo) {
  $r = Read-Host ("  amostra-{0}.wav ja existe. Regravar? (s/N)" -f $n)
  if ($r -ne "s") { Write-Host "  cancelado."; Read-Host "  Enter para sair"; exit 0 }
  Remove-Item $arquivo -Force
}

Write-Host ""
Write-Host "  ==========================================" -ForegroundColor Yellow
Write-Host "   GRAVANDO -- fale agora" -ForegroundColor Yellow
Write-Host "   aperte  Q  para parar" -ForegroundColor Yellow
Write-Host "  ==========================================" -ForegroundColor Yellow
Write-Host ""

& $ff -hide_banner -loglevel warning -f dshow -i ("audio=" + $mic) -ar 16000 -ac 1 -c:a pcm_s16le $arquivo

Write-Host ""
if (Test-Path $arquivo) {
  $bytes = (Get-Item $arquivo).Length
  $seg = [math]::Round(($bytes - 44) / 32000.0, 1)
  Write-Host ("  SALVO: amostra-{0}.wav  --  {1} segundos" -f $n, $seg) -ForegroundColor Green
  if ($seg -lt 5) { Write-Host "  ATENCAO: ficou muito curta. Vale regravar." -ForegroundColor Yellow }
} else {
  Write-Host "  nada foi gravado." -ForegroundColor Red
}
Write-Host ""
Read-Host "  Enter para fechar"
