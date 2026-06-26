@echo off
REM ───────────────────────────────────────────────────────────────
REM  수동 출력 모드 (폴백) — 자동 큐 OFF + '직접 골라 출력' 페이지 자동 오픈
REM  쓸 때: 클라우드 자동분배가 말썽일 때, 또는 특정 사람 것만 골라 뽑고 싶을 때
REM
REM  · AUTO_CLAIM=0 → 에이전트가 큐를 자동으로 안 가져감(중복 출력 방지)
REM  · 브라우저에 목록이 뜸 → [이 PC로 출력] 버튼으로 한 건씩 인쇄
REM  · 프린터 지정: 인자로 A 또는 B (기본 A). 예) print_station_manual.bat B
REM ───────────────────────────────────────────────────────────────
cd /d "%~dp0"
chcp 65001 >nul

set "ST=%~1"
if "%ST%"=="" set "ST=A"

if not exist "station_env.bat" (
  echo  [!] station_env.bat 가 없습니다. station_env.bat.example 복사 후 값 입력하세요.
  pause
  exit /b 1
)

call station_env.bat
if not defined PRINTER_A set "PRINTER_A="
if not defined PRINTER_B set "PRINTER_B="

set "STATION_ID=%ST%"
if /I "%ST%"=="A" set "PRINTER=%PRINTER_A%"
if /I "%ST%"=="B" set "PRINTER=%PRINTER_B%"
set "AUTO_CLAIM=0"

REM 렌더 포트는 print_agent.py 가 STATION_ID로 자동 계산(A=8256, B=8257)
if /I "%ST%"=="B" ( set "PICKPORT=8257" ) else ( set "PICKPORT=8256" )

echo  수동 출력 모드 시작 (STATION_ID=%STATION_ID%, 프린터=%PRINTER%)
echo  잠시 후 브라우저에 출력 목록이 열립니다…
start "" "http://127.0.0.1:%PICKPORT%/__pick"

python print_agent.py
pause
