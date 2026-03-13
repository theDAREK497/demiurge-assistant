@echo off
echo ==========================================
echo Starting Worldbuilder Wiki...
echo ==========================================

set NODE_DIR=%~dp0portable_node
set NODE_EXE=%NODE_DIR%\node.exe
set NPM_CLI=%NODE_DIR%\npm.cmd

:: Check for system Node.js
where node >nul 2>nul
if %errorlevel% equ 0 (
    echo [OK] System Node.js found.
    set NODE_CMD=node
    set NPM_CMD=npm
) else (
    if exist "%NODE_EXE%" (
        echo [OK] Portable Node.js found.
        set NODE_CMD="%NODE_EXE%"
        set NPM_CMD="%NPM_CLI%"
    ) else (
        echo [INFO] Node.js not found on the system.
        echo Starting automatic download of portable version...
        echo Please wait, downloading ~30 MB...
        
        mkdir "%NODE_DIR%" 2>nul
        powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://nodejs.org/dist/v22.14.0/node-v22.14.0-win-x64.zip' -OutFile 'node.zip'"
        
        echo Extracting files...
        powershell -Command "Expand-Archive -Path 'node.zip' -DestinationPath 'temp_node' -Force"
        xcopy /E /Y "temp_node\node-v22.14.0-win-x64\*" "%NODE_DIR%\" >nul
        
        :: Clean up temp files
        rmdir /S /Q "temp_node"
        del "node.zip" 2>nul
        
        echo [OK] Portable Node.js downloaded successfully!
        set NODE_CMD="%NODE_EXE%"
        set NPM_CMD="%NPM_CLI%"
    )
)

:: Add portable node to PATH for current session so npm install works correctly
if not "%NODE_CMD%"=="node" set "PATH=%NODE_DIR%;%PATH%"

:: Install dependencies
if not exist "node_modules\" (
    echo.
    echo Installing dependencies, this will take a few minutes on first run...
    call %NPM_CMD% install
) else (
    echo Checking dependencies...
    call %NPM_CMD% install >nul 2>nul
)

:: Start server
echo.
echo ==========================================
echo Server is starting...
echo The browser will open automatically in a few seconds.
echo If it doesn't, open manually: http://localhost:3000
echo ==========================================
start "" cmd /c "timeout /t 3 >nul && start http://localhost:3000"
call %NPM_CMD% run dev

pause
