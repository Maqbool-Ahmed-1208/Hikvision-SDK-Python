@echo off
setlocal

cd ..
call venv\Scripts\activate

python -m app.hikvision_sdk_package.nvr_camera_channel_mapping

pause
endlocal