@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM ============================================================
REM  합격 리포트 - 무대화상자 인쇄 모드 런처
REM  Chrome 을 --kiosk-printing 으로 실행 → "리포트 출력" 버튼이
REM  시스템 인쇄창 없이 "기본 프린터"로 바로 출력됨.
REM  * 같은 창에서 설문/결과/관리자 큐레이션 모두 진행해야
REM    localStorage(큐레이션)가 공유됩니다.
REM ============================================================

echo [1/2] 로컬 서버 실행 (http://localhost:8181) ...
start "passnote-server" /min python -m http.server 8181
timeout /t 1 >nul

echo [2/2] 인쇄모드 크롬 실행 ...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --kiosk-printing ^
  --user-data-dir="%~dp0_chrome_print_profile" ^
  "http://localhost:8181/live/home.html"

echo.
echo 완료. 이 창은 닫아도 됩니다.
exit
