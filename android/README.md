# Faraz Pharmacy Android 1.6.0

Package: `pk.farazpharmacy.app` · version code 7 · Android 8.0+ (API 26) · target API 35.

## Changes
- Home, Shop, Request, Track and Help bottom tabs.
- Live website homepage, portrait video, sound controls and fullscreen video.
- Dedicated medicine-request page with draft retained while switching tabs.
- Customer cart, account, order messages and quotations.
- Staff inventory photos, barcode / QR scanning and CSV / Excel imports through the live dashboard.
- Owner MP4 upload support for homepage videos.
- English / Urdu web-screen preference and App updates in the More menu.

## Build
Open this project with Android Studio using SDK 35, or use `build-apk.sh` with:
- `FARAZ_ANDROID_PLATFORM`: Android 35 platform directory.
- `FARAZ_ANDROID_TOOLS`: compatible Android build-tools directory.
- `FARAZ_KEYSTORE`: existing private Faraz Pharmacy release PKCS12 keystore.
- `FARAZ_STOREPASS_FILE`: private signing password file.
- `FARAZ_ECJ_JAR`: optional Eclipse Java compiler when javac is unavailable.

The script produces `build/faraz-pharmacy-1.6.0.apk`. Signing credentials must remain private and must never be committed. Use the existing release certificate so installed versions can update without uninstalling.

## Permissions and privacy
HTTPS only; certificate errors are rejected. No microphone or background-location permission is requested.
Camera access is restricted to the trusted staff dashboard, requires runtime permission and an explicit Allow once action, and is stopped when leaving that screen or putting the app in the background.
Delivery location is requested only by the request/checkout flow. Files are chosen through Android's document picker; no broad storage permission is used.
Staff screens retain screenshot protection. Customer and staff authentication remain separate, enforced by the pharmacy backend.

## Validation
The APK compiles, zip alignment passes, and APK v2/v3 signatures verify. Its signer matches the published 1.5.0 app; version code increases from 6 to 7.
Browser checks cover the Android request-page route and older app links. An Android device/emulator was unavailable: installation, camera permission flow and native fullscreen playback require physical-device acceptance testing.

Release APK SHA-256:
`3563fcfcdd68d885aa60c492969030d1e4b4e0225516d3dff95391a5d9982284`
