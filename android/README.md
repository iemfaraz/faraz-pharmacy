# Faraz Pharmacy Android

Android 8+ application for Faraz Pharmacy, Barikot, Swat. Application ID: `pk.farazpharmacy.app`.

The app combines native Android Home and Support screens with focused web request/tracking screens. There is no separate order database. All submissions, photos, one-time delivery-location pins, statuses and issued quotations use the existing pharmacy service and are reviewed at the existing owner dashboard. Internet access is required.

## Customer experience

- Home: native Android welcome screen, live catalogue cards, product photos, category filters and quick request actions.
- Request: existing request form and review-before-submit screen.
- Track: private reference/access-code tracking, with quotation PDF downloads.
- Support: a dedicated native help screen for WhatsApp, calls, directions, delivery information and privacy.
- Native image picker, foreground location permission and user-selected file saving.
- Home and tracking use separate views so switching tabs preserves an unsubmitted request while the app remains open. Closing the app may discard unsubmitted data.
- No advertising, background location or background notifications.
- Only HTTPS pharmacy URLs open inside the app. External maps and contact links open the relevant phone app. Certificate errors are never bypassed.
- Owner credentials do not ship in the app; dashboard use remains on the web.

## Build the signed APK from command line

Install JDK 17 and the official Android SDK platform 35 / build tools 35.0.0. Use the private release keystore backup held by the pharmacy owner. Never commit the keystore or password.

```bash
export FARAZ_ANDROID_PLATFORM=/absolute/path/to/android-sdk/platforms/android-35
export FARAZ_ANDROID_TOOLS=/absolute/path/to/android-sdk/build-tools/35.0.0
export FARAZ_KEYSTORE=/private/path/faraz-pharmacy-release.p12
export FARAZ_STOREPASS_FILE=/private/path/store-password.txt
bash build-apk.sh
```

The script compiles Java, packages resources, aligns the APK, signs with alias `faraz-pharmacy`, and verifies its signature. The output is `build/faraz-pharmacy-1.3.0.apk`.

For Android Studio, open this directory, use Gradle 8.10.2 with JDK 17, and configure release signing locally through Build > Generate Signed Bundle / APK. No signing data is present in this repository.

## Updates

Increment `versionCode` and `versionName` in both the manifest and `app/build.gradle`, use the same release signing key, then update the public download and checksum. Android updates must keep the same application ID and signing key. Do not generate a new release key for each build.

## Verification limits

Compilation, APK signing, manifest inspection and bytecode verification are performed during preparation. Physical-device testing is still needed for device-specific GPS accuracy, phone photo pickers and saving files. The app is distributed directly as an APK and is not a Google Play listing.

## Version 1.1.0

Native home screen and support, live catalogue/category browsing, add catalogue items to the request form, icon navigation, branded loading states, refresh confirmation, improved tracking-link transfer and rotation handling. Version code 2 uses the same release key as 1.0.0.

## Version 1.2.0

Removed app-install/download promotions and app-sharing menu entries from customer app screens. Added catalogue search and incremental access to all matching items, reduced thumbnail memory use, and simplified customer-facing wording. Quotation PDF saving remains available. Version code 3 uses the original release signing key.

## Version 1.3.0

Mint and emerald home with prescription upload, four category cards, catalogue search, request and order-message shortcuts. Request and tracking screens use coordinated accessible mobile styles. Submitted requests, prescription/product photos and messages use the existing HTTPS pharmacy service; staff review them in the existing dashboard. Issued quotations and changes to their items are read from that service. Android now restores both 8-digit access codes and legacy 64-character codes when switching from Request to Orders. Customer app pages have no app-download promotions.

Release verification: Java/resources compile, APK v2/v3 signatures verify, original signer matches version 1.2.0, JavaScript syntax checks pass. Physical Android testing of photo picking, location permission, request submission, quotation updates and message sending remains required. No customer requests were created during release checks.
