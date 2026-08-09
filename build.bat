@echo off
rem ===========================================================================
rem  build.bat - build a launcher executable (Windows)
rem
rem  Usage:
rem      build.bat <Name>
rem
rem  Examples:
rem      build.bat Ryujinx           builds dist\RyujinxLauncher.exe
rem
rem  What it does:
rem      1. Finds .venv - creates it and installs requirements.txt if missing
rem      2. Clears this launcher's previous build output
rem      3. Builds a single-file executable into dist\
rem
rem  Override the environment location with:  set VENV_DIR=some\other\venv
rem ===========================================================================

setlocal EnableDelayedExpansion
pushd "%~dp0"

set "NAME=%~1"
if "%VENV_DIR%"=="" set "VENV_DIR=.venv"

if "%NAME%"=="" goto :usage

set "ENTRY=src\%NAME%Launcher.py"
if not exist "%ENTRY%" goto :no_entry

set "PY=%VENV_DIR%\Scripts\python.exe"

rem ---------------------------------------------------------------------------
rem  1. Virtual environment
rem ---------------------------------------------------------------------------
if exist "%PY%" goto :venv_ready

echo [1/3] No environment at %VENV_DIR% - creating one...
call :find_base_python
if errorlevel 1 goto :no_python

%BASEPY% -m venv "%VENV_DIR%"
if errorlevel 1 goto :venv_failed
if not exist "%PY%" goto :venv_failed

echo       Installing requirements...
"%PY%" -m pip install --upgrade pip --quiet
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :deps_failed
goto :venv_done

rem A .venv left over from an older interpreter would still build, badly
"%PY%" -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if errorlevel 1 goto :old_python

:venv_ready
echo [1/3] Using environment %VENV_DIR%
rem An existing environment may predate requirements.txt - verify every build
rem and runtime dependency is present. find_spec locates them without
rem importing: importing sdl3 does network and binary resolution work.
"%PY%" -c "import importlib.util,sys; sys.exit(any(importlib.util.find_spec(m) is None for m in ('PyInstaller','customtkinter','sdl2','sdl3')))" >nul 2>&1
if not errorlevel 1 goto :venv_done
echo       Build dependencies missing - installing requirements...
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :deps_failed

:venv_done

rem ---------------------------------------------------------------------------
rem  2. Clean this launcher's previous output
rem ---------------------------------------------------------------------------
echo [2/3] Cleaning previous build of %NAME%Launcher...
if exist "build\%NAME%Launcher"     rmdir /s /q "build\%NAME%Launcher"
if exist "dist\%NAME%Launcher.exe"  del /q "dist\%NAME%Launcher.exe"
if exist "%NAME%Launcher.spec"      del /q "%NAME%Launcher.spec"

rem ---------------------------------------------------------------------------
rem  3. Build
rem ---------------------------------------------------------------------------
rem Per-launcher icon if one exists, otherwise fall back to the Ryujinx icon
set "ICON=assets\%NAME%LauncherIcon.ico"
if not exist "%ICON%" set "ICON=assets\RyujinxLauncherIcon.ico"
set "ICONARG="
if exist "%ICON%" set "ICONARG=--icon=%ICON%"

echo [3/3] Building %NAME%Launcher.exe from %ENTRY%...
echo.
"%PY%" -m PyInstaller ^
    --noconfirm ^
    --noconsole ^
    --onefile ^
    --name "%NAME%Launcher" ^
    %ICONARG% ^
    --add-data "assets;assets" ^
    --collect-all customtkinter ^
    --paths src ^
    --hidden-import Core.ControllerManagerSDL2 ^
    --hidden-import Core.ControllerManagerSDL3 ^
    "%ENTRY%"
if errorlevel 1 goto :build_failed
if not exist "dist\%NAME%Launcher.exe" goto :build_failed

echo.
echo ===========================================================================
echo  Built: dist\%NAME%Launcher.exe
echo ===========================================================================

rem The frozen exe looks for <Name>Path.config next to itself, so mirror the
rem one kept at the project root into dist\ if it is there
if exist "%NAME%Path.config" (
    copy /y "%NAME%Path.config" "dist\%NAME%Path.config" >nul
    echo  Copied %NAME%Path.config to dist\
)

goto :done

rem ===========================================================================
rem  Helpers
rem ===========================================================================
:find_base_python
rem Prefer whatever python resolves to on PATH - that is the interpreter the
rem user picked, and the one actions/setup-python installs. The py launcher is
rem only a fallback: it ignores PATH and returns the highest installed version.
rem Candidates are executed, not merely located, because the Microsoft Store
rem stub for python.exe resolves but does not run. A candidate must also be
rem Python 3.10 or newer, so an older PATH python falls through to py -3.
set "BASEPY="
python -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if not errorlevel 1 set "BASEPY=python"
if defined BASEPY exit /b 0
py -3 -c "import sys;sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1
if not errorlevel 1 set "BASEPY=py -3"
if defined BASEPY exit /b 0
exit /b 1

rem ===========================================================================
rem  Failure paths
rem ===========================================================================
:usage
echo.
echo  Usage: build.bat ^<Name^>
echo.
echo  Available launchers:
for %%F in (src\*Launcher.py) do (
    set "FOUND=%%~nF"
    echo    build.bat !FOUND:Launcher=!
)
echo.
goto :fail

:no_entry
echo.
echo  ERROR: %ENTRY% not found.
echo.
echo  Available launchers:
for %%F in (src\*Launcher.py) do (
    set "FOUND=%%~nF"
    echo    build.bat !FOUND:Launcher=!
)
echo.
goto :fail

:no_python
echo.
echo  ERROR: No Python 3.10 or newer found on PATH.
echo         Install Python 3.10+ and make sure it is on PATH,
echo         then run this script again.
echo.
goto :fail

:old_python
echo.
echo  ERROR: %VENV_DIR% uses a Python older than 3.10.
echo         Delete %VENV_DIR% and run this script again to rebuild it.
echo.
goto :fail

:venv_failed
echo.
echo  ERROR: Could not create the virtual environment at %VENV_DIR%.
echo.
goto :fail

:deps_failed
echo.
echo  ERROR: Installing requirements.txt failed.
echo.
goto :fail

:build_failed
echo.
echo  ERROR: PyInstaller build failed - see the output above.
echo.
goto :fail

:fail
popd
endlocal
exit /b 1

:done
popd
endlocal
exit /b 0
