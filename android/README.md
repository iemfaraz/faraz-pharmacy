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

The script compiles Java, packages resources, aligns the APK, signs with alias `faraz-pharmacy`, and verifies its signature. The output is `build/faraz-pharmacy-1.4.0.apk`.

For Android Studio, open this directory, use Gradle 8.10.2 with JDK 17, and configure release signing locally through Build > Generate Signed Bundle / APK. No signing data is present in this repository.

## Updates

Increment `versionCode` and `versionName` in both the manifest and `app/build.gradle`, use the same release signing key, then update the public download and checksum. Android updates must keep the same application ID and signing key. Do not generate a new release key for each build.

## Verification limits

Compilation, APK signing, manifest inspection and bytecode verification are performed during preparation. Physical-device testing is still needed for device-specific GPS accuracy, phone photo pickers and saving files. The app is distributed directly as an APK and is not a Google Play listing.

## Version 1.1.0

Native home screen and support, live catalogue/category browsing, add catalogue items to the request form, icon navigation, branded loading states, refresh confirmation, improved tracking-link transfer and rotation handling. Version code 2 uses the same release key as 1.0.0.

## Version 1.2.0

Removed app-install/download promotions and app-sharing menu entries from customer app screens. Added catalogue search and incremental access to all matching items, reduced thumbnail memory use, and simplified customer-facing wording. Quotation PDF saving remains available. Version code 3 uses the original release signing key.

## Version 1.4.0

Mint and emerald home with prescription upload, four category cards, catalogue search, request and order-message shortcuts. Request and tracking screens use coordinated accessible mobile styles. Submitted requests, prescription/product photos and messages use the existing HTTPS pharmacy service; staff review them in the existing dashboard. Issued quotations and changes to their items are read from that service. Android now restores both 8-digit access codes and legacy 64-character codes when switching from Request to Orders. Customer app pages have no app-download promotions.

Release verification: Java/resources compile, APK v2/v3 signatures verify, original signer matches version 1.2.0, JavaScript syntax checks pass. Physical Android testing of photo picking, location permission, request submission, quotation updates and message sending remains required. No customer requests were created during release checks.

## Version 1.4 owner dashboard

More → Owner dashboard opens the same server-authenticated dashboard inside a dedicated WebView. Use the owner email/password; no credentials are built into the app. Sessions stay in page memory and expire after 30 minutes. Use dashboard Log out on shared phones. Owner views enable Android FLAG_SECURE. Help includes info@farazpharmacy.com. Customer and owner WebViews are separate, and private data remains behind backend authentication.

The website and trusted geolocation/blob origins now use https://www.farazpharmacy.com and https://farazpharmacy.com. Owner file selection supports image, PDF, XLS/XLSX and CSV based on the active form. Downloads support PDF, text and inventory CSV. TLS failures are cancelled. The release APK retains the previous signing certificate and increments versionCode to 5.

Validation: Java compilation, APK signature verification and same-certificate comparison passed. Real-device UI, picker, geolocation and print testing is still required; no Android emulator/device was available in the build environment.

## Version 1.5.0 (code 6)

Home has a Shop & cart action. Published, available catalogue cards use Add to cart with the exact product ID. The dedicated customer WebView shares the website shopping service; its customer accounts have no staff privileges. More provides customer account and shopping order shortcuts. Guest tracking remains separate. Same release signer as 1.4.0. Build and APK signatures verified; physical-device UI, location and printing have not been tested in this environment.


## Customer experience in 1.7

Home / Shop / Request / My orders / Account navigation, with Help in the header. The shared website adds medicine search suggestions and spelling tolerance, account favourites and saved address text, privately linked guest requests, repeat-order review and foreground updates. Customer tokens may optionally be remembered with Android Keystore AES-GCM encryption until their existing eight-hour expiry; logout clears the vault. No background push or OTP provider is configured. Camera, location and update installation still require physical-device validation.

## Version 1.8.0 (code 9)

Redesigned, professional home screen: deep-green header with logo, location and an English / اردو toggle; catalogue search; "Have a prescription?" upload banner; Browse by form (Tablets, Suspensions, Creams, Drops); and a Track a request card. The bottom bar is now Home / Shop / Requests. Request a medicine, Customer account, Help & contact and the staff dashboard remain in the More menu. The Urdu toggle switches the website screens and the native home (right-to-left layout). The Home tab is now native and no longer loads the website homepage. Same release signer; versionCode 9.

Website and app share one design. The public site (www.farazpharmacy.com) has the same start section on its home page (`home-app-v3.js` / `.css`), with the same artwork, palette and Urdu wording. The app's Home tiles open the same links the website uses:

- Tablets / Suspensions / Creams: `shop.html?category=Medicines&form=<Form>`
- Drops: `shop.html?search=drops`
- Upload prescription: `request.html?mode=prescription` (opens on the prescription-photo choice)

The website must be deployed before the app is released, because the app loads its Shop, Request and Track screens from www.farazpharmacy.com.

Publishing a release: build with `build-apk.sh`, then from the repository root run `python3 android/publish-apk.py android/build/faraz-pharmacy-1.8.0.apk 1.8.0`. It copies the APK to `downloads/`, writes the SHA-256 file and updates the download page's link, version, size and checksum.

Verification: Java syntax parsed and resource references cross-checked; website flows (form filter, prescription mode, Urdu, in-app WebView loading) tested in a browser against a mocked catalogue. A full Android compile, APK signing and on-device UI testing are still required before publishing.
