@echo off
chcp 65001 >nul
echo   Encerrando o ditado local...
taskkill /F /T /FI "WINDOWTITLE eq ditado-local*" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*ditado.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }" >nul 2>&1
echo   Encerrado.
timeout /t 2 >nul
