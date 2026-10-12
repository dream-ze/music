#!/usr/bin/env bash
# 构建安卓 APK:静态页面内置进 APK,运行时请求 NEXT_PUBLIC_API_BASE 指向的后端。
# 用法: scripts/build_apk.sh [debug|release]   (默认 debug,装真机调试)
set -e
cd "$(dirname "$0")/../web"
export JAVA_HOME="${JAVA_HOME:-$HOME/.local/opt/jdk-17}"
export ANDROID_HOME="${ANDROID_HOME:-/opt/homebrew/share/android-commandlinetools}"
export NEXT_PUBLIC_API_BASE="${NEXT_PUBLIC_API_BASE:-https://192.tail3eff52.ts.net}"
export APP_TARGET=apk
MODE="${1:-debug}"

npx next build
[ -d android ] || npx cap add android
npx cap sync android
cd android
if [ "$MODE" = release ]; then ./gradlew assembleRelease; else ./gradlew assembleDebug; fi
find app/build/outputs/apk -name '*.apk'
echo "API base: $NEXT_PUBLIC_API_BASE"
