"""Step 1 — peek at ZIP internals so we know the column formats before ingesting."""
import json, base64, zipfile, io, sys
sys.stdout.reconfigure(encoding="utf-8")

ATTENDEES_JSON = (
    r"C:\Users\shree\.claude\projects\C--Users-shree-Claude-check"
    r"\65fe8358-c293-42b7-8891-de1523d8cd26\tool-results"
    r"\mcp-25d53f76-2777-4f78-8cd8-2cef3bb9c1da-download_file_content-1779635632998.txt"
)
REGISTRATIONS_JSON = (
    r"C:\Users\shree\.claude\projects\C--Users-shree-Claude-check"
    r"\65fe8358-c293-42b7-8891-de1523d8cd26\tool-results"
    r"\mcp-25d53f76-2777-4f78-8cd8-2cef3bb9c1da-download_file_content-1779635663688.txt"
)


def load_zip(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    raw = base64.b64decode(data["content"])
    return zipfile.ZipFile(io.BytesIO(raw))


def csv_rows(zf, name):
    with zf.open(name) as fh:
        text = fh.read().decode("utf-8-sig", errors="replace")
    return [r for r in text.splitlines() if r.strip()]


def xlsx_rows(zf, name, max_rows=10):
    import openpyxl
    with zf.open(name) as fh:
        wb = openpyxl.load_workbook(io.BytesIO(fh.read()), read_only=True, data_only=True)
        ws = wb.active
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= max_rows: break
            rows.append([str(v) if v is not None else "" for v in row])
    return rows


att_zf = load_zip(ATTENDEES_JSON)
reg_zf = load_zip(REGISTRATIONS_JSON)

# ── Attendees: show first 12 data rows of the first CSV ─────────────────────
print("=== ATTENDEES — first CSV file ===")
att_csv = next(n for n in att_zf.namelist() if n.endswith(".csv"))
print(f"  File: {att_csv}")
for row in csv_rows(att_zf, att_csv)[:14]:
    print("  |", row[:160])

print("\n=== ATTENDEES — first XLSX file ===")
att_xlsx = next(n for n in att_zf.namelist() if n.endswith(".xlsx"))
print(f"  File: {att_xlsx}")
for row in xlsx_rows(att_zf, att_xlsx, max_rows=14):
    print("  |", str(row)[:160])

# ── Registrations: show first 12 data rows of the first CSV ─────────────────
print("\n=== REGISTRATIONS — first CSV file ===")
reg_csv = next(n for n in reg_zf.namelist() if n.endswith(".csv"))
print(f"  File: {reg_csv}")
for row in csv_rows(reg_zf, reg_csv)[:14]:
    print("  |", row[:160])

print("\n=== REGISTRATIONS — first XLSX file ===")
reg_xlsx = next(n for n in reg_zf.namelist() if n.endswith(".xlsx"))
print(f"  File: {reg_xlsx}")
for row in xlsx_rows(reg_zf, reg_xlsx, max_rows=14):
    print("  |", str(row)[:160])

# ── All file names in both ZIPs ───────────────────────────────────────────────
print("\n=== ALL ATTENDEE FILES ===")
for n in att_zf.namelist(): print(" ", n)

print("\n=== ALL REGISTRATION FILES ===")
for n in reg_zf.namelist(): print(" ", n)
