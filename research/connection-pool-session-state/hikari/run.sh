#!/bin/sh
# Runs one HikariCP probe scenario. stdout is the deterministic observation record; stderr is HikariCP's own debug
# log (pool diagnostics only, never the evidence on its own).
#
# Usage: hikari/run.sh <instance-file> <scenario>
# Build first: (cd hikari && mvn -q -B package)
set -eu
DIR=$(cd "$(dirname "$0")" && pwd)
JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home}"
exec "$JAVA_HOME/bin/java" \
  -Dorg.slf4j.simpleLogger.logFile=System.err \
  -Dorg.slf4j.simpleLogger.defaultLogLevel=warn \
  -Dorg.slf4j.simpleLogger.log.com.zaxxer.hikari.pool=debug \
  -cp "$DIR/target/ssc-hikari-probe-1.0.jar:$DIR/target/lib/*" ssc.HikariProbe "$1" "$2"
