@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo Instalador do GitHub Actions Runner
echo ==============================================
echo.
echo Este arquivo vai abrir o PowerShell como Administrador.
echo A janela permanecera aberta se ocorrer algum erro.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell.exe -Verb RunAs -ArgumentList '-NoExit -NoProfile -ExecutionPolicy Bypass -File ""%~dp0instalar-runner.ps1""'"

if errorlevel 1 (
  echo.
  echo Nao foi possivel abrir o PowerShell como Administrador.
  echo Tente clicar com o botao direito neste arquivo e escolher Executar como administrador.
  echo.
  pause
)

endlocal
