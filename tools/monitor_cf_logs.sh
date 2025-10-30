#!/bin/bash

# Custom script to look at logs from run task...

# Input any app name and any task name
app_to_monitor=$1
task_to_monitor=$2

# install a better version of grep which supports --line-buffered
apk add grep 

while read -r line ; do
  echo "$line"
  if echo "$line" | grep "OUT Exit status 0"; then
    exit 0
  elif echo "$line" | grep "OUT Exit status"; then
    exit 1
  fi
done < <(cf logs "$app_to_monitor" | grep  --line-buffered "\[APP/TASK/$task_to_monitor/0\]")

