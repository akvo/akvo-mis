# Web Runtime vs Mobile App Capability Matrix

Akvo MIS forms run across two primary execution runtimes: the **Web Browser Runtime (`akvo-react-form`)** and the **Mobile App (Akvo Flow / AgriConnect on Android/iOS)**.

This matrix explicitly details supported capabilities, behavioral differences, and boundaries between the two platforms.

---

## Comprehensive Feature Comparison Matrix

| Feature / Capability | Web Browser Runtime | Mobile App (Flow / AgriConnect) | Key Details & Differences |
|---|---|---|---|
| **Form Editing & Design** | ✅ Full Visual Builder | ❌ (View / Fill only) | Form creation and schema modification happen exclusively on the Web Control Centre. |
| **Offline Data Collection** | ❌ (Requires active network) | ✅ Full Offline Queue | Mobile stores survey submissions locally in an encrypted database and syncs when internet connects. |
| **Registration ➔ Monitoring Pre-fill** | ❌ (Does not auto-pull past data) | ✅ Automatic Native Flow | When starting a linked monitoring form on mobile, past registered data is auto-populated into the form. |
| **Same-Session Cross-Question Copy** | ✅ Supported (`pre` schema) | ❌ Not active | Web runtime dynamically mirrors answers from Question A into Question B in real time within the active session. |
| **GPS Geolocation Capture** | ⚠️ Browser Geolocation API | ✅ Native Hardware GPS Chip | Mobile can enforce high-accuracy GPS thresholds (e.g. within 5 meters) before allowing capture. |
| **Photo / Camera Capture** | ✅ File picker (Upload) | ✅ Direct In-App Camera | Mobile captures live field photos with embedded timestamp and location metadata. |
| **Digital Signature Pad** | ✅ HTML5 Canvas (Mouse/Touch) | ✅ Touch Signature Pad | Both support hand-drawn signatures saved as image assets. |
| **Barcode / QR Scanning** | ❌ (Manual entry) | ✅ Hardware Camera Scanner | Mobile app can scan barcodes directly into text/input fields. |
| **Option Choice Hex Color Badges** | ✅ Renders colored tag pill | ⚠️ Standard choice layout | Visual color badges render prominently in the web form and review interface. |
| **Inline Prefix / Suffix (`addonBefore/After`)** | ✅ Inline input adornment | ✅ Inline label | Supported on both platforms for text and number fields. |

---

## Best Practices by Platform

1. **For Fieldwork in Remote Areas**: Always use the **Mobile App**. It guarantees zero data loss during network drops, caches forms locally, and captures precise hardware GPS points.
2. **For Desk Reviews & Data Entry**: Use the **Web Form**. Ideal for office-based enumerators, bulk data entry, and reviewing submitted draft records.
3. **Form Preview**: Always test form skip logic and calculations in the Form Builder **Preview Tab** before publishing.
