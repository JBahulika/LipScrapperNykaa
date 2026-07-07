#!/bin/sh
# Short commit message for gitwatch — lists changed files, no timestamps.

if [ -p /dev/stdin ] || [ ! -t 0 ]; then
  files=$(head -3 | tr '\n' ', ' | sed 's/, $//')
fi

if [ -z "$files" ]; then
  files=$(git diff --cached --name-only | head -3 | tr '\n' ', ' | sed 's/, $//')
fi

if [ -n "$files" ]; then
  echo "Update $files"
else
  echo "Update"
fi
