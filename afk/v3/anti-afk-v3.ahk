f12::
{
    Global AFKToggle
    If !AFKToggle {
        enableAFK()
    }
    Else {
        disableAFK()
    }
}

#SuspendExempt
^D::
{
	Suspend  ; Ctrl+D
	Global Suspended
	If Suspended{
        Run(voiceProgram " Anti-AFK Hotkeys Enabled",,"Hide")
		Suspended := 0
	}
	Else{
		Run(voiceProgram " Anti-AFK Hotkeys Disabled",,"Hide")
		Suspended := 1
	}
}
#SuspendExempt False

enableAFK() {
    Global AFKToggle
    Global sotHwnd

    if WinActive("Sea of Thieves") {
        sotHwnd := WinExist("A")
    }
    else {
        run(voiceProgram " Activate the hotkey when you are able to move in game.", , "Hide")
        sotHwnd := 0
        return
    }

    if activateSot() {
        Send "{Space}"
    }
    else {
        run(voiceProgram " Sea of Thieves is not running.", , "Hide")
        disableAFK()
    }
    Run(voiceProgram " AFK Mode Enabled", , "Hide")
    AFKToggle := 1
    Sleep 1000
    Send "{Space}"
    SetTimer(afkCallback, 1)
    SetTimer(reconnectCheck, 30000)
}

disableAFK() {
    Global AFKToggle
    BlockInput false
    SetTimer(afkCallback, 0)
    SetTimer(reconnectCheck, 0)
    AFKToggle := 0
    if WinActive("Sea of Thieves") {
        Send "{Space}"
    }
    Run(voiceProgram " AFK Mode Disabled", , "Hide")
    if WinActive("Sea of Thieves") {
        Sleep 1000
        Send "{Space}"
    }
}

reconnectCheck() {
    global AFKToggle
    if not checkRunning() {
        return
    }
    posX := 0
    posY := 0
    width := 0
    height := 0
    WinGetClientPos &posX, &posY, &width, &height, "Sea of Thieves"
    if width = 0 or height = 0 {
        return
    }
    x1 := width / 4
    x2 := width / 2
    x3 := width - x1
    y1 := height / 4
    y2 := height / 2
    y3 := height - y1
    checkNum := 0
    while WinActive("Sea of Thieves") and AFKToggle and checkNum < 10 {
        if (PixelGetColor(x1, y1) != 0x000000 or PixelGetColor(x2, y1) != 0x000000 or PixelGetColor(x3, y1) != 0x000000 or
            PixelGetColor(x1, y2) != 0x000000 or PixelGetColor(x3, y2) != 0x000000 or
            PixelGetColor(x1, y3) != 0x000000 or PixelGetColor(x2, y3) != 0x000000 or PixelGetColor(x3, y3) != 0x000000) {
            return
        }
        Send "{Enter}"
        Sleep 1000
        checkNum++
    }
}

calcWaitTime(startTime) {
    waitTime := 5 * 60 - (A_TickCount - startTime) / 1000
    return waitTime
}

bufferWaitTime(startTime) {
    waitTime := Max(Round(calcWaitTime(startTime), 0), 10)
    return waitTime
}

checkRunning() {
    if WinExist("Sea of Thieves") {
        return true
    }
    else {
        Run(voiceProgram " Sea of Thieves is not running.", , "Hide")
        disableAFK()
        return false
    }
}

activateSot() {
    if checkRunning() {
        try {
            WinActivate "ahk_id " sotHwnd
        } 
        catch {
            Run(voiceProgram " Sea of Thieves may have been closed.", , "Hide")
            disableAFK()
            return false
        }
        
        Sleep 500
        return true
    }
    else {
        return false
    }
}

afkCallback()
{
    Global AFKToggle
    if not checkRunning() {
        return
    }

    startTime := A_TickCount
    while calcWaitTime(startTime) > 0 and AFKToggle {
        sotActive := WinWaitActive("Sea of Thieves", , bufferWaitTime(startTime))
        if sotActive {
            inputTest := InputHook("L1 V T" bufferWaitTime(startTime))
            inputTest.Start()
            inputTest.Wait()
            if not WinActive("Sea of Thieves") {
                continue
            }
            else if inputTest.Input == "" {
                continue
            }
            else {
                Sleep 60000 ; Sleep for a minute so we dont have to check for input every second
                return
            }
        }
        else {
            continue
        }
    }

    afkActions()
}

afkActions() {
    Global AFKToggle
    if !AFKToggle {
        return
    }

    BlockInput true

    current := WinExist("A")
    sotWindow := WinExist("Sea of Thieves")

    if not activateSot() {
        return
    }

    if sotWindow == current {
        current := 0
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
        try{
            WinActivate "ahk_id " current
        }
    }

    BlockInput false
}
