@echo off
REM ───────────────────────────────────────────────────────────────
REM  수동 출력 모드 (자동 큐 OFF) — 한 화면에서 목록 보고 직접 골라 출력
REM  · 프린터 2대(PRINTER_A / PRINTER_B)면 각 줄에 [🖨 A로] [🖨 B로] 버튼이 뜸
REM  · 1대만 입력했거나 비우면 [이 PC로 출력] 한 버튼(기본 프린터)
REM  · 자동분배가 불안할 때 사람이 직접 통제하는 가장 확실한 방식
REM
REM  준비: station_env.bat 에 SUPABASE_SERVICE_KEY + PRINTER_A / PRINTER_B 입력
REM ───────────────────────────────────────────────────────────────
cd /d "%~dp0"
chcp 65001 >nul

if not exist "station_env.bat" (
  echo  [!] station_env.bat 가 없습니다. station_env.bat.example 복사 후 값 입력하세요.
  pause
  exit /b 1
)

call station_env.bat

REM 수동 단일 인스턴스: 자동 큐 OFF, 포트 고정(8250), A/B 둘 다 이 인스턴스가 보유
set "AUTO_CLAIM=0"
set "STATION_ID=MANUAL"
set "AGENT_PORT=8250"

echo  수동 출력 모드 시작…
echo    PRINTER_A = %PRINTER_A%
echo    PRINTER_B = %PRINTER_B%
echo  잠시 후 브라우저에 출력 목록(http://127.0.0.1:8250/__pick)이 열립니다.
echo  목록에서 출력할 사람의 [🖨 A로]/[🖨 B로] 버튼을 누르면 해당 프린터로 나갑니다.
echo.
start "" "http://127.0.0.1:8250/__pick"

python print_agent.py
pause
