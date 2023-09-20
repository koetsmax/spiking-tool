#Requires AutoHotkey >=2.0
#SingleInstance Off
#WinActivateForce
DetectHiddenWindows 1
DetectHiddenText 1
SendMode "Play"
SetKeyDelay 25, 25, "Play"
SetMouseDelay 25, "Play"
CoordMode "Pixel", "Window"

AFKToggle := 0

previous := WinGetList(A_ScriptFullPath " ahk_class AutoHotkey")
for id in previous{
	if id != A_ScriptHwnd{
		WinClose("ahk_id " id)
	}
}

if !InStr(A_AhkPath, "_UIA") {
	Run("*uiAccess " A_ScriptFullPath)
	ExitApp
}

f1::
{
	Global AFKToggle
	If !AFKToggle {
		if WinActive("Sea of Thieves") {
			Send "{Space}"
		}
		else if  WinExist("Sea of Thieves") {
			WinActivate "Sea of Thieves"
			Sleep 500
			WinActivate "Sea of Thieves"
			Sleep 500
			Send "{Space}"
		}
		else{
			AFKToggle := 0
			return
		}
		AFKToggle := 1
		Sleep 1000
		Send "{Space}"
		SetTimer(afkCallback, 1)
		SetTimer(reconnectCheck, 30000)
	}
	Else {
		SetTimer(afkCallback, 0)
		SetTimer(reconnectCheck, 0)
		AFKToggle := 0
		if WinActive("Sea of Thieves") {
			Send "{Space}"
		}
		if WinActive("Sea of Thieves") {
			Sleep 1000
			Send "{Space}"
		}
	}
}

reconnectCheck(){
	if WinActive("Sea of Thieves") {
		global AFKToggle
		WinGetPos ,, &width, &height, "Sea of Thieves"
		color := PixelGetColor(width/2, 100)
		while color == 0x000000 and afkToggle {
			Send "{Enter}"
			Sleep 1000
			color := PixelGetColor(width/2, 100)
		}
	}
}

afkCallback()
{
	Global AFKToggle
	if not WinExist("Sea of Thieves") {
		SetTimer(afkCallback, 0)
		SetTimer(reconnectCheck, 0)
		AFKToggle := 0
		return
	}

	startTime := A_TickCount
	sotActive := WinWaitActive("Sea of Thieves",,5*60)
	if sotActive {
        waitTime := 5 * 60 - (A_TickCount - startTime) / 1000
        while waitTime > 0 {
            waitTime := Max(Round(waitTime, 0), 10)
            inputTest := InputHook("L1 V T" waitTime)
            inputTest.Start()
            inputTest.Wait()
            if not WinActive("Sea of Thieves") {
                waitTime := 5 * 60 - (A_TickCount - startTime) / 1000
				waitTime := Max(Round(waitTime, 0), 10)
                sotActive := WinWaitActive("Sea of Thieves", , waitTime)
                if not sotActive {
                    afkActions()
                    return
                }
                else{
                    waitTime := 5 * 60 - (A_TickCount - startTime) / 1000
                    continue
                }
            }
            else if inputTest.Input == "" {
                afkActions()
                return
            }
            else {
                Sleep 60000
                return
            }
        }
        afkActions()
        return
	}
	else {
		afkActions()
		return
	}
}

afkActions(){
	Global AFKToggle
	if !AFKToggle {
		return
	}

	BlockInput true

	current := WinExist("A")
	sotWindow := WinExist("Sea of Thieves")


	if sotWindow == 0 {
        BlockInput false
		SetTimer(afkCallback, 0)
		SetTimer(reconnectCheck, 0)
		AFKToggle := 0
		return
	}
	else if sotWindow == current {
		current := 0
	}
	else{
		WinActivate "Sea of Thieves"
		Sleep 500
		WinActivate "Sea of Thieves"
		Sleep 500
	}
	
	reconnectCheck()

	multiplier := Random(.25, 1)
	duration := multiplier * 500
	version := Random(1, 7)
	if version == 1 {
		SendInput "{a down}"
		Sleep duration
		SendInput "{a up}"
	}
	if version == 2 {
		SendInput "{d down}"
		Sleep duration
		SendInput "{d up}"
	}
	if version == 3 {
		SendInput "{w down}"
		Sleep duration
		SendInput "{w up}"
	}
	if version == 4 {
		SendInput "{w Down}"
		Sleep duration
		SendInput "{w up}"
	}
	if version == 5 {
		SendInput "{s Down}"
		Sleep duration
		SendInput "{s up}"
	}
	if version == 6 {
		SendInput "{1 Down}"
		Sleep duration
		SendInput "{1 up}"
	}
	if version == 7 {
		SendInput "{2 Down}"
		Sleep duration
		SendInput "{2 up}"
	}

	if current {
		WinActivate "ahk_id " current
	}

	BlockInput false
}