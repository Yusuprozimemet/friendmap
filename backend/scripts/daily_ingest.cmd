@echo off
REM Daily ingest wrapper for Task Scheduler.
REM
REM A wrapper rather than pointing the task straight at python.exe: Task
REM Scheduler has nowhere to put stdout, and a job whose output vanishes is a
REM job nobody notices has been failing. Everything lands in logs\ingest.log.
REM
REM Also note this runs the alert digests, because run_daily calls them at the
REM end ? so this task is what makes saved-search alerts fire at all.

setlocal

REM scripts\ -> backend\
set "BACKEND=%~dp0.."
set "LOGDIR=%BACKEND%\logs"
set "LOG=%LOGDIR%\ingest.log"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

REM Python writes UTF-8; without this the em dashes in summaries come out as
REM mojibake in the log.
set "PYTHONIOENCODING=utf-8"

REM Keep one previous run's log; unbounded appending eventually eats the disk
REM on a job that runs every day forever. The size test lives inside the
REM `if exist` block because cmd expands %%~zA while parsing the whole line ?
REM outside it, a missing log leaves an empty operand and a parse error.
if exist "%LOG%" (
    for %%A in ("%LOG%") do (
        if %%~zA GTR 5242880 move /y "%LOG%" "%LOG%.1" >nul
    )
)

echo. >> "%LOG%"
echo ================================================== >> "%LOG%"
echo run started %DATE% %TIME% >> "%LOG%"

pushd "%BACKEND%"
".venv\Scripts\python.exe" -u manage.py ingest --days 7 >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
popd

echo run finished %DATE% %TIME% with exit code %RC% >> "%LOG%"
exit /b %RC%
