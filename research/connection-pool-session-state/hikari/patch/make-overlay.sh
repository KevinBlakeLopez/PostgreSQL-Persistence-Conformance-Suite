#!/bin/sh
# Builds hikari/target/hikari-7.1.0-evict-on-failed-reset.jar, the overlay run-patched.sh puts first on the classpath:
# HikariCP 7.1.0's ProxyConnection from Maven Central's sources jar, with the ProxyConnection hunk of
# hikaricp-7.1.0-evict-on-failed-reset.diff applied. Run (cd hikari && mvn -q -B package) first, for target/lib.
#
# The hunk is applied with patch(1), not git apply: inside this repository, git apply resolves paths from the
# repository root and silently skips the file.
set -eu
DIR=$(cd "$(dirname "$0")/.." && pwd)
JAVA_HOME="${JAVA_HOME:-/opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home}"
WORK="$DIR/target/patch-work"
rm -rf "$WORK" "$DIR/target/patch-classes"
mkdir -p "$WORK/src" "$DIR/target/patch-classes"
curl -sSfL -o "$WORK/sources.jar" https://repo1.maven.org/maven2/com/zaxxer/HikariCP/7.1.0/HikariCP-7.1.0-sources.jar
(cd "$WORK/src" && unzip -q ../sources.jar com/zaxxer/hikari/pool/ProxyConnection.java)
awk '/^diff --git / { keep = ($0 ~ /ProxyConnection\.java/) } keep' "$DIR/patch/hikaricp-7.1.0-evict-on-failed-reset.diff" > "$WORK/proxyconnection.diff"
(cd "$WORK/src" && patch -p4 -s < "$WORK/proxyconnection.diff")
grep -q 'poolEntry.markEvicted();' "$WORK/src/com/zaxxer/hikari/pool/ProxyConnection.java" || { echo "the change was not applied" >&2; exit 1; }
"$JAVA_HOME/bin/javac" --release 11 -nowarn -cp "$DIR/target/lib/*" -d "$DIR/target/patch-classes" \
  "$WORK/src/com/zaxxer/hikari/pool/ProxyConnection.java"
(cd "$DIR/target/patch-classes" && "$JAVA_HOME/bin/jar" cf ../hikari-7.1.0-evict-on-failed-reset.jar com)
echo "built $DIR/target/hikari-7.1.0-evict-on-failed-reset.jar"
