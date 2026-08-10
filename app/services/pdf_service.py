import os

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def generate_certificate(data: dict):

    os.makedirs("certificates", exist_ok=True)

    sal_id = data["sal_id"]
    certificate_number = data["certificate_number"]
    owner = data["owner"]
    asset_type = data["asset_type"]
    estimated_value = data["estimated_value"]
    registration_date = data["registration_date"]
    asset_details = data["asset_details"]

    filename = f"certificates/{sal_id}.pdf"

    pdf = canvas.Canvas(filename)
    pdf.setTitle("SAL Digital Certificate")

    # =====================================================
    # BORDER
    # =====================================================

    pdf.setStrokeColor(HexColor("#003366"))
    pdf.setLineWidth(3)
    pdf.rect(25, 25, 560, 790)


# =====================================================
    # WATERMARK
    # =====================================================

    watermark_path = os.path.join(
        os.getcwd(),
        "assets",
        "watermark.png"
    )
    if os.path.exists(watermark_path):

        watermark = ImageReader(watermark_path)

        pdf.saveState()
        pdf.drawImage(
            watermark,
            165, # Move slightly to the right
            300,  # Move much higher
            width=220, # Make it smaller
            height=220,
            preserveAspectRatio=True,
            mask="auto"
        )
        pdf.restoreState()



 # =====================================================
    # LOGO
    # =====================================================

    logo_path = os.path.join(os.getcwd(), "assets", "logo.png")

    if os.path.exists(logo_path):

        logo = ImageReader(logo_path)

        pdf.drawImage(
            logo,
            50,         #Moved slightly right
            748,         # moved higher
            width=55,    # slightly smaller
            height=55,
            preserveAspectRatio=True,
            mask="auto"
        )

    # =====================================================
    # HEADER
    # =====================================================

    pdf.setFillColor(HexColor("#003366"))

    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(
        120,
        790,
        "SOVEREIGN ASSET LEDGER"
    )

    pdf.setFont("Helvetica", 14)
    pdf.drawString(
        120,
        770,
        "Digital Asset Certificate"
    )# m

    pdf.setLineWidth(2)

    pdf.line(
        45,
        742,
        550,
        742
    )

    # =====================================================
    # CERTIFICATE DETAILS
    # =====================================================

    pdf.setFont("Helvetica-Bold", 12)

    pdf.drawString(60, 715, f"Certificate No: {certificate_number}")
    pdf.drawString(60, 695, f"SAL ID: {sal_id}")
    pdf.drawString(60, 675, f"Owner: {owner}")
    pdf.drawString(60, 655, f"Asset Type: {asset_type}")
    pdf.drawString(60, 635, f"Registration Date: {registration_date}")

    pdf.line(
        60,
        620,
        550,
        620
    )
    # =====================================================
    # ASSET DETAILS
    # =====================================================

    pdf.setFont("Helvetica-Bold", 15)

    pdf.drawString(
        60,
        595,
        "Asset Details"
    )

    pdf.setFont("Helvetica", 11)

    y = 570

    for key, value in asset_details.items():

        pdf.drawString(
            70,
            y,
            f"{key.replace('_',' ').title()}: {value}"
        )

        y -= 20

    pdf.line(
        60,
        y - 5,
        550,
        y - 5
    )

    y -= 30

    pdf.setFont("Helvetica-Bold", 12)

    pdf.drawString(
        60,
        y,
        f"Estimated Value: {estimated_value}"
    )

    y -= 25

    pdf.drawString(
        60,
        y,
        "Status: VERIFIED"
    )

    # =====================================================
    # QR CODE
    # =====================================================

    qr_path = os.path.join(
        os.getcwd(),
        "qrcodes",
        f"{sal_id}.png"
    )

    if os.path.exists(qr_path):

        qr = ImageReader(qr_path)

        pdf.drawImage(
            qr,
            395,
            y - 15,
            width=105,
            height=105,
            preserveAspectRatio=True,
            mask="auto"
        )

        pdf.setFont("Helvetica", 9)

        pdf.drawCentredString(
            447,
            y - 28,
            "Scan to Verify"
        )

    # =====================================================
    # SIGNATURE
    # =====================================================

    y -= 90

    pdf.setFont("Helvetica", 10)

    pdf.line(
        60,
        y,
        220,
        y
    )

    pdf.drawString(
        60,
        y - 15,
        "Authorized Signature"
    )

    pdf.drawString(
        60,
        y - 32,
        "Sovereign Asset Ledger Africa"
    )

    # =====================================================
    # OFFICIAL SEAL
    # =====================================================

    pdf.setStrokeColor(HexColor("#003366"))
    pdf.setLineWidth(2)

    pdf.circle(
        500,
        y - 10,
        28
    )

    pdf.drawCentredString(
        500,
        y - 45,
        "Official Seal"
    )

    # =====================================================
    # BLOCKCHAIN
    # =====================================================

    pdf.setFillColor(HexColor("#003366"))

    pdf.drawString(
        60,
        y - 80,
        "Blockchain Verification:"
    )

    pdf.setFillColor(HexColor("#666666"))

    pdf.drawString(
        200,
        y - 80,
        "Pending Blockchain Anchoring"
    )

    pdf.save()

    return filename