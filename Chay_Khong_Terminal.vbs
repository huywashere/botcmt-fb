Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = scriptDir

' 0 = SW_HIDE (ẩn cửa sổ đen hoàn toàn), False = không đợi kết thúc
WshShell.Run "python """ & scriptDir & "\main.py""", 0, False
