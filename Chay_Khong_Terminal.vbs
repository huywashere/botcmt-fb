Dim WshShell, fso, currentDir
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = currentDir

' Chạy ngầm 100% không mở màn hình đen
WshShell.Run "cmd /c start """" pythonw """ & currentDir & "\main.py""", 0, False
