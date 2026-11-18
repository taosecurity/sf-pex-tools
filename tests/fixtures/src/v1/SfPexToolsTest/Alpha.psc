; SPDX-License-Identifier: MIT
; Test script for sf-pex-tools. Written for the tests; it does nothing useful in a game.
ScriptName SfPexToolsTest:Alpha extends ScriptObject

Struct Mission
    String Name = "Survey"
    Int Reward = 100
    Float Weight = 1.5
    Bool Done = False
EndStruct

Guard CountGuard ProtectsFunctionLogic

Int Property MaxCount = 5 Auto Const
String Property Label = "alpha" Auto
Mission[] Missions
Int Count = 0

Int Function AddMission(String asName, Int aiReward)
    If Missions == None
        Missions = new Mission[0]
    EndIf
    Mission m = new Mission
    m.Name = asName
    m.Reward = aiReward
    Missions.Add(m)
    LockGuard CountGuard
        Count += 1
    EndLockGuard
    Debug.Trace("[SfPexToolsTest] added " + asName + " for " + aiReward)
    Return Count
EndFunction

Mission[] Function BigOnes()
    Return Missions.GetAllMatchingStructs("Reward", 100)
EndFunction

Bool Function TryCount()
    TryLockGuard CountGuard
        Count += 1
        Return True
    EndTryLockGuard
    Return False
EndFunction

Float Function Score(Int aiA, Int aiB, Float afScale)
    Float total = (aiA * 2 + aiB) as Float
    If total > MaxCount as Float && aiB != 0
        total = total / afScale
    ElseIf aiA < 0
        total = -total
    EndIf
    Return total
EndFunction
