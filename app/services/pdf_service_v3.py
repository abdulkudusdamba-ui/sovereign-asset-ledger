import hashlib
from datetime import datetime
import os

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


NAVY = HexColor("#003366")
GOLD = HexColor("#C9A227")
LIGHT_GREY = HexColor("#D9D9D9")


def generate_certificate(data: dict):

    os.makedirs("certificates", exist_ok=True)

    sal_id = data["sal_id"]
    certificate_number = data["certificate_number"]
    owner = data["owner"]
    asset_type = data["asset_type"]
    estimated_value = data["estimated_value"]
    registration_date = data["registration_date"]
    asset_details = data["asset_details"]

    # =====================================================
    # SECURITY INFORMATION
    # =====================================================

    certificate_hash = hashlib.sha256(
        f"{sal_id}{certificate_number}{owner}{registration_date}".encode()
    ).hexdigest().upper()

    verification_code = certificate_hash[:12]

    issued_at = datetime.utcnow().strftime(
        "%d %B %Y %H:%M UTC"
    )

    registrar_id = "SAL-REG-0001"

    # Continue with the rest of your PDF code here...

    filename = f"certificates/{sal_id}.pdf"

    pdf = canvas.Canvas(
        filename,
        pagesize=A4
    )

    width, height = A4

    pdf.setTitle("SAL Digital Asset Certificate")

    # =====================================================
    # PAGE BACKGROUND
    # =====================================================

    pdf.setFillColor(HexColor("#FFFFFF"))
    pdf.rect(
        0,
        0,
        width,
        height,
        fill=1,
        stroke=0
    )
    # =====================================================
    # OUTER BORDER
    # =====================================================

    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(3)

    pdf.roundRect(
        20,
        20,
        width - 40,
        height - 40,
        8,
        stroke=1,
        fill=0
    )

    # =====================================================
    # INNER BORDER
    # =====================================================

    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1.5)

    pdf.roundRect(
        32,
        32,
        width - 64,
        height - 64,
        6,
        stroke=1,
        fill=0
    )

    # =====================================================
    # TOP GOLD BAR
    # =====================================================

    pdf.setFillColor(GOLD)

    pdf.rect(
        32,
        height - 60,
        width - 64,
        6,
        stroke=0,
        fill=1
    )

    # =====================================================
    # BOTTOM GOLD BAR
    # =====================================================

    pdf.rect(
        32,
        30,
        width - 64,
        6,
        stroke=0,
        fill=1
    )
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
            width / 2 - 120,
            height / 2 - 120,
            width=240,
            height=240,
            preserveAspectRatio=True,
            mask="auto"
        )

        pdf.restoreState()

    # =====================================================
    # LOGO
    # =====================================================

    logo_path = os.path.join(
        os.getcwd(),
        "assets",
        "logo.png"
    )

    if os.path.exists(logo_path):

        logo = ImageReader(logo_path)

        pdf.drawImage(
            logo,
            45,
            height - 95,
            width=55,
            height=55,
            preserveAspectRatio=True,
            mask="auto"
        )

    # =====================================================
    # HEADER
    # =====================================================

    pdf.setFillColor(NAVY)

    pdf.setFont("Helvetica-Bold", 24)

    pdf.drawCentredString(
        width / 2,
        height - 55,
        "SOVEREIGN ASSET LEDGER"
    )

    pdf.setFont("Helvetica", 14)

    pdf.drawCentredString(
        width / 2,
        height - 78,
        "Digital Asset Certificate"
    )

    pdf.setFillColor(GOLD)

    pdf.setFont("Helvetica-Bold", 10)

    pdf.drawCentredString(
        width / 2,
        height - 95,
        "Secure | Verify | Protect | Trust"
    )

    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)

    pdf.line(
        45,
        height - 110,
        width - 45,
        height - 110
    )
     # =====================================================
    # CERTIFICATE INFORMATION
    # =====================================================

    info_top = height - 145

    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 16)

    pdf.drawString(
        50,
        info_top,
        "Certificate Information"
    )

    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)

    pdf.line(
        50,
        info_top - 8,
        width - 50,
        info_top - 8
    )

    pdf.setFont("Helvetica-Bold", 11)

    label_x = 60
    value_x = 220

    y = info_top - 35

    certificate_info = [
        ("Certificate No", certificate_number),
        ("SAL ID", sal_id),
        ("Owner", owner),
        ("Asset Type", asset_type),
        ("Registration Date", registration_date),
    ]

    for label, value in certificate_info:

        pdf.setFillColor(NAVY)

        pdf.drawString(
            label_x,
            y,
            f"{label}:"
        )

        pdf.setFillColor(HexColor("#222222"))

        pdf.drawString(
            value_x,
            y,
            str(value)
        )

        y -= 22

    # Leave some space before the next section
    y -= 15
      # =====================================================
    # VEHICLE INFORMATION
    # =====================================================

    panel_top = y

    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 16)

    pdf.drawString(
        50,
        panel_top,
        "Vehicle Information"
    )

    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)

    pdf.line(
        50,
        panel_top - 8,
        width - 50,
        panel_top - 8
    )

    # -----------------------------------------------------
    # Information Box
    # -----------------------------------------------------

    box_y = panel_top - 190

    pdf.setFillColor(HexColor("#FAFAFA"))

    pdf.roundRect(
        50,
        box_y,
        width - 100,
        170,
        8,
        stroke=1,
        fill=1
    )
    print("Asset Details:", asset_details)

    pdf.setFont("Helvetica-Bold", 11)

    fields = [
        ("Registration Number", asset_details.get("registration_number", "N/A")),
        ("VIN", asset_details.get("vin", "N/A")),
        ("Manufacturer", asset_details.get("manufacturer", "N/A")),
        ("Model", asset_details.get("model", "N/A")),
        ("Year", asset_details.get("year", "N/A")),
        ("Engine Number", asset_details.get("engine_number", "N/A")),
        ("Color", asset_details.get("color", "N/A")),
        ("Estimated Value", f"GHS {estimated_value:,.2f}")
    ]

    label_x = 65
    value_x = 250
    row_y = panel_top - 35

    for label, value in fields:

        pdf.setFillColor(NAVY)
        pdf.drawString(label_x, row_y, label + ":")

        pdf.setFillColor(HexColor("#222222"))
        pdf.drawString(value_x, row_y, str(value))

        row_y -= 20

    # Position for the next section
    section_y = box_y - 145
    # =====================================================
    # QR VERIFICATION PANEL
    # =====================================================

    qr_box_width = 220
    qr_box_height = 120

    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(1.5)

    pdf.roundRect(
        50,
        section_y,
        qr_box_width,
        qr_box_height,
        6,
        stroke=1,
        fill=0
    )

    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 12)

    pdf.drawCentredString(
        160,
        section_y + 98,
        "QR Verification"
    )

    qr_path = os.path.join(
        os.getcwd(),
        "qrcodes",
        f"{sal_id}.png"
    )

    if os.path.exists(qr_path):

        qr = ImageReader(qr_path)

        pdf.drawImage(
            qr,
            70,
            section_y + 18,
            width=70,
            height=70,
            preserveAspectRatio=True,
            mask="auto"
        )

    pdf.setFont("Helvetica", 9)

    pdf.drawString(
        150,
        section_y + 55,
        "Scan to Verify"
    )

    pdf.drawString(
        150,
        section_y + 40,
        sal_id
    )

       # =====================================================
    # OFFICIAL SAL SEAL PANEL
    # =====================================================

    seal_x = width - 270

    pdf.roundRect(
        seal_x,
        section_y,
        220,
        qr_box_height,
        6,
        stroke=1,
        fill=0
    )

    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 12)

    pdf.drawCentredString(
        seal_x + 110,
        section_y + 98,
        "Official SAL Seal"
    )

    # =====================================================
    # REAL SAL EMBOSSED SEAL
    # =====================================================

    seal_path = os.path.join(
        os.getcwd(),
        "assets",
        "seal.png"
    )

    if os.path.exists(seal_path):

        seal = ImageReader(seal_path)

        pdf.drawImage(
            seal,
            seal_x + 65,
            section_y + 20,
            width=90,
            height=70,
            preserveAspectRatio=True,
            mask="auto"
        )

    else:

        pdf.setFont(
            "Helvetica",
            9
        )

        pdf.setFillColor(
            HexColor("#666666")
        )

        pdf.drawCentredString(
            seal_x + 110,
            section_y + 55,
            "SAL SEAL"
        )

    # Save position for footer
    footer_y = section_y - 95
    # =====================================================
    # =====================================================
    # REGISTRAR & SECURITY FOOTER
    # =====================================================

    footer_y = 125

    # -----------------------------------------------------
    # FOOTER DIVIDER
    # -----------------------------------------------------

    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1)

    pdf.line(
        50,
        footer_y + 55,
        width - 50,
        footer_y + 55
    )

    # -----------------------------------------------------
    # AUTHORIZED REGISTRAR
    # -----------------------------------------------------

    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 11)

    pdf.drawString(
        50,
        footer_y + 35,
        "Authorized Registrar"
    )

    # Signature
    signature_path = os.path.join(
        os.getcwd(),
        "assets",
        "signature.png"
    )

    if os.path.exists(signature_path):

        signature = ImageReader(signature_path)

        pdf.drawImage(
            signature,
            50,
            footer_y + 5,
            width=80,
            height=25,
            preserveAspectRatio=True,
            mask="auto"
        )

    # Signature line
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(0.8)

    pdf.line(
        50,
        footer_y + 3,
        210,
        footer_y + 3
    )

    pdf.setFillColor(HexColor("#333333"))
    pdf.setFont("Helvetica", 9)

    pdf.drawString(
        50,
        footer_y - 12,
        "Sovereign Asset Ledger Africa"
    )

    # -----------------------------------------------------
    # SECURITY INFORMATION
    # -----------------------------------------------------

    security_x = 300

    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 9)

    pdf.drawString(
        security_x,
        footer_y + 35,
        "Certificate Version:"
    )

    pdf.drawString(
        security_x,
        footer_y + 20,
        "Verification:"
    )

    pdf.drawString(
        security_x,
        footer_y + 5,
        "Blockchain:"
    )

    pdf.drawString(
        security_x,
        footer_y - 10,
        "Verification Code:"
    )

    pdf.drawString(
        security_x,
        footer_y - 25,
        "Issued:"
    )

    pdf.drawString(
        security_x,
        footer_y - 40,
        "Registrar ID:"
    )

    # -----------------------------------------------------
    # SECURITY VALUES
    # -----------------------------------------------------

    value_x = 405

    pdf.setFillColor(HexColor("#333333"))
    pdf.setFont("Helvetica", 9)

    pdf.drawString(
        value_x,
        footer_y + 35,
        "SAL v4.0"
    )

    pdf.setFillColor(HexColor("#008000"))

    pdf.drawString(
        value_x,
        footer_y + 20,
        "VERIFIED"
    )

    pdf.setFillColor(HexColor("#333333"))

    pdf.drawString(
        value_x,
        footer_y + 5,
        "Pending Blockchain Anchoring"
    )

    pdf.drawString(
        value_x,
        footer_y - 10,
        verification_code
    )

    pdf.drawString(
        value_x,
        footer_y - 25,
        issued_at
    )

    pdf.drawString(
        value_x,
        footer_y - 40,
        registrar_id
    )

    # -----------------------------------------------------
    # CERTIFICATE HASH
    # -----------------------------------------------------

    hash_y = footer_y - 60

    pdf.setFillColor(NAVY)
    pdf.setFont("Helvetica-Bold", 8)

    pdf.drawString(
        50,
        hash_y,
        "Certificate Hash:"
    )

    pdf.setFillColor(HexColor("#555555"))
    pdf.setFont("Helvetica", 7)

    pdf.drawString(
        135,
        hash_y,
        certificate_hash[:70]
    )

    # -----------------------------------------------------
    # VERIFICATION URL
    # -----------------------------------------------------

    pdf.setFillColor(HexColor("#555555"))
    pdf.setFont("Helvetica", 7)

    pdf.drawCentredString(
        width / 2,
        45,
        f"Verify this certificate at https://sal.africa/verify/{sal_id}"
    )


    pdf.save()

    return filename