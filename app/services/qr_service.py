import os
import qrcode

BASE_URL = "http://127.0.0.1:8000"


def generate_qr(sal_id: str):
    os.makedirs("qrcodes", exist_ok=True)

    verification_url = f"{BASE_URL}/verify/{sal_id}"

    filename = f"qrcodes/{sal_id}.png"

    img = qrcode.make(verification_url)

    img.save(filename)

    return filename