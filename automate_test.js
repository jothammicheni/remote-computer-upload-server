"auto";

// =========================================================
// AUTOX.JS AUTOMATION — REGION-BASED CLICK VERSION
// Author: ChatGPT (Educational Use)
// ---------------------------------------------------------
//  - 3 region-specific random clicks (bottom, mid, top)
//  - Stable clicks using gestures()
//  - Fast but reliable automation speed
//  - Detects 3 vertical green lines (light–dark)
//  - Stops automatically & shows overlay
//  - Prevents sleep mode
// =========================================================
//66
device.keepScreenOn(3600 * 1000); // prevent sleep for 1 hour

// ---------------- CONFIG ----------------
const SWIPE_DISTANCE = device.height * 0.25;
const SWIPE_DURATION = 250;
const REFRESH_WAIT = 400;
const MAX_CAPTURE_RETRIES = 2;

const GREEN_MIN_PIXELS_PER_BUCKET = 10;
const GREEN_DELTA = 40;
const GREEN_MIN = 70;
const GREEN_MAX = 255;
const BUCKET_WIDTH = 25;
const SAMPLE_STEP = 6;

// --- CLICK REGIONS ---
const BOTTOM_REGION = {
    top: Math.floor(device.height * 0.75),
    bottom: Math.floor(device.height * 0.95),
    left: Math.floor(device.width * 0.25),
    right: Math.floor(device.width * 0.75)
};
const MID_REGION = {
    top: Math.floor(device.height * 0.45),
    bottom: Math.floor(device.height * 0.65),
    left: Math.floor(device.width * 0.25),
    right: Math.floor(device.width * 0.75)
};
const TOP_REGION = {
    top: Math.floor(device.height * 0.10),
    bottom: Math.floor(device.height * 0.30),
    left: Math.floor(device.width * 0.25),
    right: Math.floor(device.width * 0.75)
};

let paused = false, running = false;
let overlayBitmap = null;

// ========== FLOATY UI ==========
let window = floaty.window(
    <frame>
        <vertical>
            <text id="title" text="🟢 AutoX.js Automation"
                textColor="#FFFFFF"
                background="#006400"
                gravity="center"
                textSize="18sp"
                w="*" h="40"/>
            <img id="overlay" w="*" h="wrap_content"/>
            <horizontal>
                <button id="restart" text="🔄 Restart"
                    textSize="14sp" w="0" weight="1"
                    background="#444444" textColor="#FFFFFF"/>
                <button id="save" text="💾 Save"
                    textSize="14sp" w="0" weight="1"
                    background="#333333" textColor="#FFFFFF"/>
            </horizontal>
        </vertical>
    </frame>
);
window.setPosition(device.width - 420, 80);
try { window.setTouchable(true); } catch (e) {}

if (!requestScreenCapture()) {
    toast("❌ Screenshot permission denied.");
    exit();
}

// ========= BUTTON ACTIONS =========
window.save.click(() => {
    if (overlayBitmap) {
        let path = "/sdcard/overlay_" + new Date().getTime() + ".png";
        images.save(overlayBitmap, path);
        toast("Overlay saved: " + path);
    } else toast("No overlay to save.");
});

window.restart.click(() => {
    if (paused) {
        toast("Restarting automation...");
        ui.run(() => {
            window.title.setText("🟢 AutoX.js Automation");
            window.title.setBackgroundColor(colors.parseColor("#006400"));
        });
        paused = false;
        running = true;
        threads.start(startAutomation);
    } else toast("Already running...");
});

// ========= FUNCTIONS =========
function randInt(a, b) { return Math.floor(Math.random() * (b - a + 1)) + a; }

function regionClick(region) {
    let x = randInt(region.left, region.right);
    let y = randInt(region.top, region.bottom);
    gestures([0, 120, [x, y], [x, y]]);
    sleep(randInt(200, 300));
}

function swipeUp(distance, duration) {
    let x = device.width / 2;
    let y = Math.floor(device.height * 0.75);
    swipe(x, y, x, y - distance, duration);
}

function captureScreenSafe(retries) {
    for (let i = 0; i < retries; i++) {
        let img = captureScreen();
        if (img) return img;
        sleep(120);
    }
    return null;
}

function mmToPx(mm) {
    let dpi = device.dpi || 440;
    return Math.round((mm / 25.4) * dpi);
}

// ---- GREEN DETECTION ----
function isGreenShade(r, g, b) {
    return (g >= GREEN_MIN && g <= GREEN_MAX && g - r > GREEN_DELTA && g - b > GREEN_DELTA);
}

function analyzeGreen(img) {
    let w = img.getWidth(), h = img.getHeight();
    let buckets = {};
    for (let y = 0; y < h; y += SAMPLE_STEP) {
        for (let x = 0; x < w; x += SAMPLE_STEP) {
            let p = img.pixel(x, y);
            let r = colors.red(p), g = colors.green(p), b = colors.blue(p);
            if (isGreenShade(r, g, b)) {
                let bucket = Math.floor(x / BUCKET_WIDTH);
                buckets[bucket] = (buckets[bucket] || 0) + 1;
            }
        }
    }
    let centers = [];
    for (let k in buckets) {
        if (buckets[k] >= GREEN_MIN_PIXELS_PER_BUCKET) {
            centers.push({ x: (k * BUCKET_WIDTH) + Math.floor(BUCKET_WIDTH / 2), count: buckets[k] });
        }
    }
    centers.sort((a, b) => a.x - b.x);
    return centers;
}

function hasThreeSeparateLines(centers) {
    if (centers.length < 3) return false;
    let minSepPx = mmToPx(2);
    for (let i = 0; i <= centers.length - 3; i++) {
        let a = centers[i], b = centers[i + 1], c = centers[i + 2];
        if ((b.x - a.x) >= minSepPx && (c.x - b.x) >= minSepPx)
            return [a, b, c];
    }
    return false;
}

function makeOverlayBitmap(img, detectedCenters) {
    let w = img.getWidth(), h = img.getHeight();
    let canvas = new Canvas(w, h);
    let paint = new Paint();
    canvas.drawImage(img, 0, 0, paint);

    let circlePaint = new Paint();
    circlePaint.setColor(colors.argb(200, 0, 255, 0));
    circlePaint.setStyle(Paint.Style.FILL);
    let radius = Math.max(35, Math.round(Math.min(w, h) * 0.04));

    for (let c of detectedCenters) {
        for (let y = 60; y < h - 60; y += 60) {
            canvas.drawCircle(c.x, y, radius, circlePaint);
        }
    }
    return canvas.toImage();
}

function showOverlay(bitmap) {
    overlayBitmap = bitmap;
    ui.run(() => {
        window.overlay.setImageBitmap(bitmap);
        let desiredW = Math.min(device.width * 0.8, bitmap.getWidth());
        window.overlay.setLayout(desiredW, Math.floor(device.height * 0.6));
    });
}

// ========= START =========
if (!dialogs.confirm("⚠️ Start automation?", "Automation will begin in 5 seconds.")) {
    toast("Canceled by user.");
    exit();
}

toast("Starting in 5 seconds...");
sleep(5000);
toast("Automation started.");
running = true;
threads.start(startAutomation);

// ========= MAIN LOOP =========
function startAutomation() {
    while (running) {
        // 1️⃣ Region-based random clicks
        regionClick(BOTTOM_REGION);  // near bottom
        regionClick(MID_REGION);     // mid
        regionClick(TOP_REGION);     // near top

        // 2️⃣ Swipe up once
        swipeUp(SWIPE_DISTANCE, SWIPE_DURATION);
        sleep(REFRESH_WAIT);

        // 3️⃣ Capture & analyze
        let img = captureScreenSafe(MAX_CAPTURE_RETRIES);
        if (!img) continue;

        let centers = analyzeGreen(img);
        let trio = hasThreeSeparateLines(centers);

        if (trio) {
            let overlay = makeOverlayBitmap(img, trio);
            let overlayPath = "/sdcard/green_detected_" + new Date().getTime() + ".png";
            images.save(overlay, overlayPath);
            showOverlay(overlay);

            ui.run(() => {
                window.title.setText("🟢 Paused: 3 Green Lines Found");
                window.title.setBackgroundColor(colors.parseColor("#228B22"));
            });
            toast("Paused — 3 green lines detected.\nOverlay saved.");
            paused = true;
            running = false;
            break;
        }

        // 4️⃣ Go back and swipe again
        back();
        sleep(REFRESH_WAIT);
        swipeUp(SWIPE_DISTANCE, SWIPE_DURATION);
        sleep(REFRESH_WAIT);
    }
}
