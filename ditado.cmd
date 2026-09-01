@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem --- derruba instancia anterior, janela e tudo ---
rem Dois filtros porque cada um pega o que o outro perde:
rem   taskkill por titulo    -> mata a janela de console e a arvore inteira (/T),
rem                             incluindo o cmd hospedeiro que ficaria orfao;
rem   powershell por cmdline -> pega o python desde o instante em que nasce,
rem                             antes de a janela existir e ter titulo.
taskkill /F /T /FI "WINDOWTITLE eq ditado-local*" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*ditado.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }" >nul 2>&1

rem --- sobe em janela propria ---
rem O servico nao termina: fica de pe esperando o atalho. START abre a janela e
rem este .cmd devolve o controle na hora -- sem isso, quem o chamar de dentro de
rem outro programa (o Claude, por exemplo) fica preso para sempre.
rem
rem Caminhos ABSOLUTOS: quando este .cmd e chamado por outro script ou por um
rem atalho, o diretorio corrente nao e necessariamente o desta pasta, e caminho
rem relativo falha com "nao reconhecido como comando".
start "ditado-local" cmd /k ""%~dp0.venv\Scripts\python.exe" -u "%~dp0ditado.py""

echo.
echo   Ditado local subindo na janela "ditado-local".
echo   Espere aparecer "pronto" nela, e entao segure Ctrl+Win para falar.
echo.
echo   Para encerrar: feche aquela janela, ou rode parar.cmd
echo.
