#!/bin/bash -e

control_files=(*/"debian/control")

for control_file in "${control_files[@]}"; do
    source=$(sed -En "\|^Source:|s|.*: ([a-z-]+)|\1|p" "$control_file")
    echo "> $control_file : $source"
    grep "^Package:\|^Architecture:" "$control_file"
    echo
done
