# Run On Pixel 8

## Scope

This guide is for the Android MVP client shell under `android_client/`.

It is a product-serving path only. It does **not** run benchmark tooling or OpenAI evaluation on the phone.

## What you need

- Android Studio Hedgehog or newer
- a Pixel 8 with Developer Options enabled
- the Mac and Pixel 8 on the same Wi-Fi network
- the local API running on your Mac

## 1. Start the local API on your Mac

```bash
cd "/Users/adelie/Documents/New project/database"
python3 -m uvicorn api:app --host 0.0.0.0 --port 8010
```

Use `0.0.0.0` here so your Pixel 8 can reach the API over the local network.

## 2. Find your Mac's local IP address

Run one of these on the Mac:

```bash
ipconfig getifaddr en0
```

or, if needed:

```bash
ipconfig getifaddr en1
```

Suppose the result is `192.168.1.25`.

## 3. Point the Android app at that IP

Edit:

- `/Users/adelie/Projects/gemma4good/android_client/app/src/main/java/good/gemma4good/android/AppConfig.kt`

Change:

```kotlin
const val BASE_URL: String = "http://10.0.2.2:8010/"
```

To:

```kotlin
const val BASE_URL: String = "http://192.168.1.25:8010/"
```

Notes:

- `10.0.2.2` is for the Android emulator only.
- A physical Pixel 8 must use the Mac's LAN IP or another reachable hostname.

## 4. Open the Android project in Android Studio

Open this folder as a project:

- `/Users/adelie/Projects/gemma4good/android_client`

Let Gradle sync finish.

## 5. Enable USB debugging on Pixel 8

On the phone:

1. Go to `Settings -> About phone`.
2. Tap `Build number` 7 times.
3. Go back to `Settings -> System -> Developer options`.
4. Turn on `USB debugging`.

## 6. Connect and trust the device

- Connect the Pixel 8 by USB.
- Accept the computer trust prompt on the phone if shown.
- Confirm the device appears in Android Studio's device selector.

## 7. Run the app

In Android Studio:

- select the `app` run configuration
- choose the connected Pixel 8
- press `Run`

## 8. Test the MVP flow

The current MVP supports:

- user ID
- region
- one selected input mode at a time
- product name
- URL mode
- text mode
- image-intake placeholder fields
- OCR review text before sending the request
- sending the request to `/analyze-product`
- rendering the returned summary fields

Example tests:

### URL mode
- Product name: `ProtectME Fabric Protector`
- Product page URL: a reachable Amazon or Weee product page
- Leave text/OCR fields empty

### Text mode
- Product name: `Waterproof baby bib`
- Typed text: `PVC waterproof bib. WARNING: Cancer and Reproductive Harm - www.P65Warnings.ca.gov. DEHP; PVC; soft vinyl layer.`

### Image mode placeholder
- Product name: `Waterproof baby bib`
- Enter image placeholder URIs or notes
- Tap `Create OCR review draft`
- Replace the draft with reviewed OCR text before analysis

## 9. Expected result

The current MVP should return a summary including:

- inferred category
- inferred material
- recommendation bucket
- recommendation reason
- concern sources
- review reasons if any

## Current limitation

This Android MVP now includes a lightweight image-intake placeholder and OCR review step, but it still does not yet include real on-device image picking or OCR.

It does not yet include:

- real multi-image picker integration
- on-device OCR execution
- category-confirm UI
- saved history screens
- review-queue browsing UI

Those are next-shell features, not contract blockers.
