#!/bin/sh
# Bundles web/src/app.js (with viem) into web/app.js so the page does not wait on a CDN.
# Needs: npm i viem@2.57.3 esbuild (in any folder on NODE_PATH or alongside).
npx esbuild "$(dirname "$0")/src/app.js" --bundle --minify --format=esm --target=es2020 --outfile="$(dirname "$0")/app.js"
