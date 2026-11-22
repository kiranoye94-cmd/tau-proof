@echo off
REM Run both Tau proofs. Needs: git clone of IDNI/tau-testnet at a54a346,
REM python venv with requirements-min.txt installed, PYTHONPATH set to the repo.
setlocal
if "%PYTHONPATH%"=="" (
  echo [X] PYTHONPATH is not set. Point it at your tau-testnet checkout, e.g.
  echo     set PYTHONPATH=C:\Users\intel\tau-testnet
  exit /b 2
)
echo === #164 decline vote counted as approval ===
python "%~dp0repro_164_decline_vote.py"
echo [exit=%ERRORLEVEL%]  ^(1 = vulnerable, 0 = fixed^)
echo.
echo === #108 254-address width deadlock ===
python "%~dp0repro_108_deadlock.py"
echo [exit=%ERRORLEVEL%]
endlocal
