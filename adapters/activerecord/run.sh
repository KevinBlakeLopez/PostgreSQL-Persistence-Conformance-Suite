#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -x /opt/homebrew/opt/ruby/bin/ruby ]; then
  PATH="/opt/homebrew/opt/ruby/bin:$PATH"
  export PATH
fi
exec bundle exec ruby main.rb
