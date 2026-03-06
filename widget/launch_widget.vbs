
' Stock Widget Auto-Launcher
' Runs python -m widget.main silently (no terminal window)
Dim shell
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\stock_project"
shell.Run "C:\Users\asd46\anaconda3\python.exe -m widget.main", 0, False
Set shell = Nothing
