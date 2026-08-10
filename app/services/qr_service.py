import os
import qrcode

BASE_URL = "https://crispy-parakeet-696xr6g75gwv3xvj4-8000.app.github.dev"

def generate_qr(sal_id: str):
    os.makedirs("qrcodes", exist_ok=True)

    verification_url = f"{BASE_URL}/verify/{sal_id}"
    print("QR CONTENT:", verification_url)

    filename = f"qrcodes/{sal_id}.png"

    img = qrcode.make(verification_url)
    img.save(filename)

    return filename