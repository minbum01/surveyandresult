@echo off
REM ───────────────────────────────────────────────────────────────
REM  프린트 스테이션 1개 실행 — Supabase 인쇄 큐를 폴링해서 자동 출력
REM  (설계: 클라우드_인쇄시스템_설계.md §5  /  코드: print_agent.py)
REM
REM  사용:  print_station.bat A      (프린터 A로 출력하는 인스턴스)
REM         print_station.bat B      (프린터 B로 출력하는 인스턴스)
REM         print_station.bat        (인자 없으면 A, 기본 프린터로 — 1대 테스트용)
REM
REM  ※ 프린터 2대 동시 운영은  print_station_2printers.bat  더블클릭이 편함.
REM  준비물(이 PC): 레포 폴더 전체 + Chrome + tools\SumatraPDF.exe + 프린터
REM  최초 1회: station_env.bat.example → station_env.bat 복사 후 키/프린터명 입력
REM ───────────────────────────────────────────────────────────────
cd /d "%~dp0"
chcp 65001 >nul

set "ST=%~1"
if "%ST%"=="" set "ST=A"

if not exist "station_env.bat" (
  echo.
  echo  [!] station_env.bat 가 없습니다.
  echo      station_env.bat.example 을 복사해 station_env.bat 로 만들고
  echo      SUPABASE_SERVICE_KEY ^(service_role 키^) 와 프린터명을 채운 뒤 다시 실행하세요.
  echo.
  pause
  exit /b 1
)

call station_env.bat
if not defined PRINTER_A set "PRINTER_A="
if not defined PRINTER_B set "PRINTER_B="

set "STATION_ID=%ST%"
if /I "%ST%"=="A" set "PRINTER=%PRINTER_A%"
if /I "%ST%"=="B" set "PRINTER=%PRINTER_B%"

echo ================================================
echo   프린트 스테이션 시작
echo     STATION_ID = %STATION_ID%
echo     PRINTER    = %PRINTER%   (빈값=기본 프린터)
echo     URL        = %SUPABASE_URL%
echo ================================================
echo   * 인쇄 모니터(관리자 페이지)에서 이 스테이션이 초록불로 뜨면 정상.
echo   * 이 창을 닫으면 이 프린터 인쇄가 멈춥니다. 행사 동안 켜두세요.
echo.

python print_agent.py

echo.
echo  [에이전트 종료됨] 오류로 멈췄다면 위 메시지를 확인하세요.
pause
