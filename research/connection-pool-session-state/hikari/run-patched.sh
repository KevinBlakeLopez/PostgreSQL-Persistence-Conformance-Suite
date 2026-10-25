#!/bin/sh
# Runs one probe scenario against HikariCP 7.1.0 with the one-line change in patch/hikaricp-7.1.0-evict-on-failed-reset.diff:
# close() marks the pool entry evicted when the rollback or the state reset throws. The overlay jar comes first on
# the classpath. stderr includes the JVM's class-load line for ProxyConnection, which names the jar it came from.
#
# Usage: hikari/run-patched.sh <instance-file> <scenario>
# Build first: (cd hikari && mvn -q -B package && patch/make-overlay.sh)
set -eu
DIR=$(cd "$(dirname "$0")" && pwd)
JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home}"
exec "$JAVA_HOME/bin/java" \
  -Xlog:class+load=info:stderr \
  -Dorg.slf4j.simpleLogger.logFile=System.err \
  -Dorg.slf4j.simpleLogger.defaultLogLevel=warn \
  -Dorg.slf4j.simpleLogger.log.com.zaxxer.hikari.pool=debug \
  -cp "$DIR/target/hikari-7.1.0-evict-on-failed-reset.jar:$DIR/target/ssc-hikari-probe-1.0.jar:$DIR/target/lib/*" \
  ssc.HikariProbe "$1" "$2"
