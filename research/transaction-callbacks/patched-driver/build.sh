#!/bin/sh
# Builds what the patched-driver experiment ran:
# - PHP 8.5.12 from the php.net release tarball, configured with only what the Laravel scenarios need;
# - pdo_pgsql from that tarball's ext/pdo_pgsql, as a shared module, twice: unchanged (stock.so), and
#   with pdo_pgsql-reject-rollback-tag.patch (patched.so).
# Both modules are built the same way, with phpize, against the same PHP and libpq.
#
#   sh research/transaction-callbacks/patched-driver/build.sh <work directory> [<libpq prefix>]
#
# The work directory receives the download, the source, the PHP install, the logs and the two modules.
# libpq defaults to Homebrew's. Then, for example:
#
#   CB_PHP=<work>/php/bin/php CB_PHP_ARGS="-n -dextension=<work>/patched.so" CB_DRIVER_LABEL=patched \
#     node research/transaction-callbacks/laravel/run.mjs --repeat=3
set -eu

WORK=$(cd "${1:?usage: build.sh <work directory> [<libpq prefix>]}" && pwd)
LIBPQ=${2:-$(brew --prefix libpq)}
HERE=$(cd "$(dirname "$0")" && pwd)
VERSION=8.5.12
# php.net's published checksum for php-8.5.12.tar.xz.
SHA256=08bc2eba2a588654ade1357174aa646b761556c862dda0678345ee29ed481209
JOBS=$(sysctl -n hw.ncpu 2>/dev/null || nproc)

cd "$WORK"
curl -sSfL -o "php-$VERSION.tar.xz" "https://www.php.net/distributions/php-$VERSION.tar.xz"
echo "$SHA256  php-$VERSION.tar.xz" | shasum -a 256 -c -
rm -rf "php-$VERSION"
tar -xJf "php-$VERSION.tar.xz"

cd "php-$VERSION"
./configure --prefix="$WORK/php" --disable-all --enable-cli --disable-cgi --disable-phpdbg --without-pear \
  --enable-pdo --enable-ctype --enable-filter --enable-mbstring --disable-mbregex --enable-tokenizer \
  > "$WORK/configure.log"
make -j"$JOBS" > "$WORK/make.log"
make install > "$WORK/install.log"

for variant in stock patched; do
  rm -rf "$WORK/pdo_pgsql-$variant"
  cp -R "$WORK/php-$VERSION/ext/pdo_pgsql" "$WORK/pdo_pgsql-$variant"
  cd "$WORK/pdo_pgsql-$variant"
  if [ "$variant" = patched ]; then
    patch -p3 < "$HERE/pdo_pgsql-reject-rollback-tag.patch"
  fi
  "$WORK/php/bin/phpize" > "$WORK/phpize-$variant.log"
  ./configure --with-php-config="$WORK/php/bin/php-config" --with-pdo-pgsql="$LIBPQ" > "$WORK/configure-$variant.log"
  make -j"$JOBS" > "$WORK/make-$variant.log"
  cp modules/pdo_pgsql.so "$WORK/$variant.so"
done

"$WORK/php/bin/php" -n -dextension="$WORK/patched.so" -r 'echo "patched.so loads: PDO drivers ", implode(",", PDO::getAvailableDrivers()), "\n";'
shasum -a 256 "$WORK/stock.so" "$WORK/patched.so"
