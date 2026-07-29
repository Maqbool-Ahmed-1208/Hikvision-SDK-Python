@echo off
setlocal

cd ..
call venv\Scripts\activate

python -m app.examples.playback_extractor

pause
endlocal