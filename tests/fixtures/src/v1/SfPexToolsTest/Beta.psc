; SPDX-License-Identifier: MIT
; Test script for sf-pex-tools. Written for the tests; it does nothing useful in a game.
ScriptName SfPexToolsTest:Beta extends ScriptObject

Group Settings
    Int Property Limit = 3 Auto
    String Property Greeting = "hello" Auto Const
EndGroup

Group Counters
    Int Property Seen Hidden
        Int Function Get()
            Return SeenCount
        EndFunction
        Function Set(Int aiValue)
            SeenCount = aiValue
        EndFunction
    EndProperty
EndGroup

Int SeenCount = 0
String[] Names

Function Note(String asName)
    If Names == None
        Names = new String[0]
    EndIf
    Names.Add(asName)
    SeenCount += 1
    If SeenCount >= Limit
        GotoState("Full")
    EndIf
EndFunction

String Function Describe()
    Return Greeting + ": " + Names.Length + " of " + Limit
EndFunction

State Full
    Function Note(String asName)
        Debug.Trace("[SfPexToolsTest] full, ignored " + asName)
    EndFunction
EndState
