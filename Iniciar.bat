@echo off
REM Atalho de inicializacao do Comanda Digital.
REM Roda o launcher (que verifica atualizacoes do GitHub antes de subir o servidor).
REM Sem janela de console: usa pythonw.exe.

cd /d "%~dp0"
start "" pythonw.exe launcher.py
