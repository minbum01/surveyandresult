' 합격 리포트 - 무창 인쇄모드 (콘솔창 없음, 인쇄서버 자동실행)
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = base
sh.Run "cmd /c python print_server.py", 0, False
WScript.Sleep 1500
chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
sh.Run """" & chrome & """ --user-data-dir=""" & base & "\_chrome_print_profile"" http://localhost:8181/live/home.html", 1, False
