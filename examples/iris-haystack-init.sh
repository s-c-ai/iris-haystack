#!/usr/bin/env bash

set -Eeo pipefail

# The container runs this script as irisowner after IRIS has started. Terminal
# access therefore uses OS authentication and does not expose bootstrap
# credentials on the command line.
/usr/irissys/bin/iris session IRIS -U%SYS <<'OBJECTSCRIPT'
set properties("Enabled")=1
set sc=##class(Security.Services).Modify("%Service_CallIn",.properties)
if 'sc { do ##class(%SYSTEM.OBJ).DisplayError(sc) do ##class(%SYSTEM.Process).Terminate(,1) }

set sc=1
set exists=##class(Security.Users).Exists("demo",.user)
if 'exists { set sc=##class(Security.Users).Create("demo","%All","demo") }
if exists,$isobject(user) { set user.PasswordExternal="demo",sc=user.%Save() }
if 'sc { do ##class(%SYSTEM.OBJ).DisplayError(sc) do ##class(%SYSTEM.Process).Terminate(,1) }

halt
OBJECTSCRIPT

touch /tmp/iris-haystack-ready
