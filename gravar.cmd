@echo off
chcp 65001 >nul
title gravar amostra de voz
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0gravar.ps1"
