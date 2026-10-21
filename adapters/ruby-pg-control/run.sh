#!/bin/sh
# The harness starts this with a PATH that may still prefer /usr/bin/ruby.
# Homebrew Ruby 4.0.7 is the interpreter this adapter was pinned against.
set -eu
cd "$(dirname "$0")"
if [ -x /opt/homebrew/opt/ruby/bin/ruby ]; then
  PATH="/opt/homebrew/opt/ruby/bin:$PATH"
  export PATH
fi
exec bundle exec ruby main.rb
