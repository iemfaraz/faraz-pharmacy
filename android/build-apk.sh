#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${FARAZ_ANDROID_PLATFORM:?Set FARAZ_ANDROID_PLATFORM to SDK android-35 folder}"
: "${FARAZ_ANDROID_TOOLS:?Set FARAZ_ANDROID_TOOLS to SDK build-tools folder}"
: "${FARAZ_KEYSTORE:?Set FARAZ_KEYSTORE to your private release .p12 file}"
: "${FARAZ_STOREPASS_FILE:?Set FARAZ_STOREPASS_FILE to the private password file}"
rm -rf build/classes build/gen build/dex
mkdir -p build/classes build/gen build/dex
"$FARAZ_ANDROID_TOOLS/aapt2" compile --dir app/src/main/res -o build/resources.zip
"$FARAZ_ANDROID_TOOLS/aapt2" link -o build/unsigned.apk -I "$FARAZ_ANDROID_PLATFORM/android.jar" --manifest app/src/main/AndroidManifest.xml --java build/gen build/resources.zip
find app/src/main/java build/gen -name '*.java' -print > build/sources.list
if command -v javac >/dev/null 2>&1; then
 javac -encoding UTF-8 -source 8 -target 8 -classpath "$FARAZ_ANDROID_PLATFORM/android.jar" -d build/classes @build/sources.list
else
 : "${FARAZ_ECJ_JAR:?JDK javac or FARAZ_ECJ_JAR is required}"
 java -jar "$FARAZ_ECJ_JAR" -proc:none -encoding UTF-8 -source 8 -target 8 -bootclasspath "$FARAZ_ANDROID_PLATFORM/android.jar:$FARAZ_ANDROID_TOOLS/core-lambda-stubs.jar" -d build/classes @build/sources.list
fi
python3 - <<'PYZIP'
import zipfile
from pathlib import Path
with zipfile.ZipFile('build/classes.jar','w',zipfile.ZIP_DEFLATED) as z:
 for f in Path('build/classes').rglob('*.class'):z.write(f,f.relative_to('build/classes'))
PYZIP
"$FARAZ_ANDROID_TOOLS/d8" --lib "$FARAZ_ANDROID_PLATFORM/android.jar" --min-api 26 --output build/dex build/classes.jar
(cd build/dex && zip -q -u ../unsigned.apk classes.dex)
"$FARAZ_ANDROID_TOOLS/zipalign" -f -p 4 build/unsigned.apk build/aligned.apk
"$FARAZ_ANDROID_TOOLS/apksigner" sign --ks "$FARAZ_KEYSTORE" --ks-key-alias faraz-pharmacy --ks-pass "file:$FARAZ_STOREPASS_FILE" --out build/faraz-pharmacy-1.1.0.apk build/aligned.apk
"$FARAZ_ANDROID_TOOLS/apksigner" verify --verbose build/faraz-pharmacy-1.1.0.apk
sha256sum build/faraz-pharmacy-1.1.0.apk
