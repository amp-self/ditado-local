@echo off
title Historico do Ditado
cd /d "%~dp0"
set TENTATIVAS=0

REM ---- o servico ja esta de pe? ----
REM A porta 4772 e do servidor de historico, que roda dentro do proprio servico
REM de ditado. Se ela responde, o ditado esta rodando -- as duas coisas sobem e
REM caem juntas, e por isso este unico atalho serve para as duas.
call :escutando
if "%LIVE%"=="1" goto :pronto

echo Subindo o ditado local (o modelo leva alguns segundos)...
call "%~dp0ditado.cmd" >nul

REM Espera a porta responder, ate ~40 segundos: a carga do modelo na GPU leva
REM entre 5 e 14 segundos, e a maquina fria demora mais. Nao usa TIMEOUT, que
REM quebra quando a entrada esta redirecionada; PING funciona em qualquer contexto.
:esperar
ping -n 2 127.0.0.1 >nul
call :escutando
if "%LIVE%"=="1" goto :pronto
set /a TENTATIVAS+=1
if %TENTATIVAS% LSS 40 goto :esperar

echo.
echo NAO SUBIU. Abra a janela "ditado-local" para ver o erro, ou rode:
echo   type "%~dp0historico\servico.log"
pause
exit /b 1

:pronto
set NAV="C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist %NAV% set NAV="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist %NAV% set NAV="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

start "" %NAV% --app=http://127.0.0.1:4772 --window-size=980,1200
exit /b 0

:escutando
set LIVE=0
netstat -ano -p tcp | findstr /c:"127.0.0.1:4772" | findstr /c:"LISTENING" >nul 2>&1
if not errorlevel 1 set LIVE=1
goto :eof
