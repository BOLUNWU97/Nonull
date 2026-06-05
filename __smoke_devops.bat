@echo off
cd /d "C:\Users\EDY\Desktop\智能体"
python.exe __smoke_devops.py > __smoke_devops.out 2>&1
echo EXIT=%ERRORLEVEL%
