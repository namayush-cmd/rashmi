from flask import Flask, render_template, jsonify, request
import requests
import json
import gspread
import os
import time
import schedule
import threading
from oauth2client.service_account import ServiceAccountCredentials
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from datetime import datetime, timedelta
from twilio.rest import Client

app = Flask(__name__)   # ✅ पहले app बनाओ

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER   # ✅ अब use करो

SCOPES = ['https://www.googleapis.com/auth/drive']


# ==============================
# ✅ SHEET1 URL (Dashboard)
# ==============================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1n41G7B2OHqYACPqC0hAepeMEYcgIs8Ekgyunv5fm2EI/gviz/tq?tqx=out:json&sheet=Sheet1"


# ==============================
# ✅ HOME PAGE
# ==============================
@app.route("/")
def index():
    return render_template("Rashmi.html")

@app.route("/add-case-page")
def add_case_page():
    return render_template("add_case.html")

# ==============================
# ✅ FETCH DATA (Sheet1)
# ==============================
@app.route("/data")
def get_data():
    try:
        response = requests.get(SHEET_URL)
        text = response.text

        if "google.visualization.Query.setResponse" not in text:
            return jsonify({"error": "Sheet not public"})

        json_data = json.loads(text[47:-2])

        # ✅ Headers
        columns = [col['label'] for col in json_data['table']['cols']]

        rows = []
        total_cols = len(columns)

        for r in json_data['table']['rows']:
            row = [""] * total_cols

            for i, c in enumerate(r['c']):
                if c and 'v' in c:
                    val = c['v']

                    # =========================
                    # 🔥 DATE NORMALIZATION
                    # =========================

                    # 1. Google Date format
                    if isinstance(val, str) and val.startswith("Date("):
                        parts = val.replace("Date(", "").replace(")", "").split(",")
                        val = f"{parts[2]:0>2}-{int(parts[1])+1:0>2}-{parts[0]}"

                    # 2. YYYY-MM-DD → DD-MM-YYYY
                    elif isinstance(val, str) and "-" in val:
                        parts = val.split("-")
                        if len(parts) == 3 and len(parts[0]) == 4:
                            val = f"{parts[2]}-{parts[1]}-{parts[0]}"

                    # 3. DD/MM/YYYY → DD-MM-YYYY
                    elif isinstance(val, str) and "/" in val:
                        parts = val.split("/")
                        if len(parts) == 3:
                            val = f"{parts[0]:0>2}-{parts[1]:0>2}-{parts[2]}"

                    row[i] = val

            rows.append(row)

        return jsonify({
            "columns": columns,
            "rows": rows
        })

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({"error": str(e)})
        
@app.route("/add", methods=["POST"])
def add_data():
    try:
        data = request.form

        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "rashmi-496902-110c50649025.json", scope
        )

        client = gspread.authorize(creds)

        sheet = client.open_by_key(
            "1n41G7B2OHqYACPqC0hAepeMEYcgIs8Ekgyunv5fm2EI"
        ).worksheet("Sheet1")

        # ✅ FILE UPLOAD
        file_links = []

        for i in range(1, 13):
            file = request.files.get(f"doc{i}")

            if file and file.filename != "":
                filename = f"{int(time.time())}_{file.filename}"
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

                file.save(filepath)

                link = upload_to_drive(filepath, filename)
                file_links.append(link)
            else:
                file_links.append("")

        # ✅ ROW BUILD
        row = [
            data.get("district",""),
            data.get("caseType",""),
            data.get("filing",""),
            data.get("reg",""),
            data.get("year",""),

            data.get("filingDate",""),
            data.get("regDate",""),
            data.get("firstHearing",""),
            data.get("nextHearing",""),

            data.get("caseStage",""),
            data.get("court",""),
            data.get("petitioner",""),
            data.get("respondent",""),
            data.get("section",""),
            data.get("decision",""),

            *file_links,

            data.get("date",""),
            data.get("hindi1",""),
            data.get("hindi2",""),
            data.get("hindi3","")
        ]

        sheet.append_row(row, value_input_option="USER_ENTERED")

        return {"status": "success"}

    except Exception as e:
        return {"status": "error", "message": str(e)}
        
@app.route("/update2", methods=["POST"])
def update_data():
    try:
        data = request.form

        row_number = int(data.get("row"))

        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "rashmi-496902-110c50649025.json", scope
        )

        client = gspread.authorize(creds)

        sheet = client.open_by_key(
            "1n41G7B2OHqYACPqC0hAepeMEYcgIs8Ekgyunv5fm2EI"
        ).worksheet("Sheet1")

        # ✅ OLD FILES PRESERVE
        old_row = sheet.row_values(row_number)
        file_links = old_row[15:27] if len(old_row) >= 27 else [""] * 12

        # ✅ ROW BUILD
        row = [
            data.get("district",""),
            data.get("caseType",""),
            data.get("filing",""),
            data.get("reg",""),
            data.get("year",""),

            data.get("filingDate",""),
            data.get("regDate",""),
            data.get("firstHearing",""),
            data.get("nextHearing",""),

            data.get("caseStage",""),
            data.get("court",""),
            data.get("petitioner",""),
            data.get("respondent",""),
            data.get("section",""),
            data.get("decision",""),

            *file_links,

            data.get("date",""),
            data.get("hindi1",""),
            data.get("hindi2",""),
            data.get("hindi3","")
        ]

        # ✅ CLEAN DATA
        row = [str(x) if x else "" for x in row]

        # ✅ HEADER LENGTH (NO -1)
        headers_len = len(sheet.row_values(1))

        row = row[:headers_len] + [""] * (headers_len - len(row))

        # ✅ COLUMN LETTER FUNCTION
        def get_column_letter(n):
            result = ""
            while n > 0:
                n, remainder = divmod(n - 1, 26)
                result = chr(65 + remainder) + result
            return result

        end_col = get_column_letter(headers_len)

        # ✅ FINAL RANGE
        range_name = f"A{row_number}:{end_col}{row_number}"

        sheet.update(range_name, [row])

        return {"status": "success"}

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==============================
# ✅ AUTH FUNCTION
# ==============================
def get_drive_service():
    creds = None

    # 🔹 token file (auto login)
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # 🔹 login flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret_688764053502-t3ce0hcjdva8j2vnhgpjcb0n3u9clju9.apps.googleusercontent.com.json',
                SCOPES
            )
            creds = flow.run_local_server(port=8080)

        # 🔹 save token
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('drive', 'v3', credentials=creds)


def upload_to_drive(filepath, filename):
    service = get_drive_service()

    file_metadata = {
        'name': filename,
    }

    media = MediaFileUpload(filepath, resumable=True)

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    file_id = file.get('id')

    service.permissions().create(
        fileId=file_id,
        body={'type': 'anyone', 'role': 'reader'}
    ).execute()

    return f"https://drive.google.com/file/d/{file_id}/view"

sent_dates = set()

def check_hearing_dates():
    today = datetime.now().date()

    for row in data:
        next_date = parse_date(row[8])

        if not next_date:
            continue

        key = (row[2], next_date)

        if next_date - timedelta(days=3) == today and key not in sent_dates:
            send_whatsapp(row)
            sent_dates.add(key)

def run_scheduler():
    schedule.every().day.at("09:00").do(check_hearing_dates)

    while True:
        schedule.run_pending()
        time.sleep(60)


threading.Thread(target=run_scheduler, daemon=True).start()

def send_message(row):
    client = Client("ACf4360b7cb5051ecdfe8744ef6a78a95a", "5a8827ec851ffa11f9dbb64f072ab393")

    message = client.messages.create(
        body=f"Reminder: Hearing on {row[8]} for case {row[2]}",
        from_="+1234567890", 
        to="+919818584627"
    )
    print("SMS Sent:", message.sid)
    

def send_whatsapp(row):
    client = Client("ACf4360b7cb5051ecdfe8744ef6a78a95a", "5a8827ec851ffa11f9dbb64f072ab393")

    message = client.messages.create(
        body=f"Reminder: Hearing on {row[8]} for case {row[2]}",
        from_="whatsapp:+14155238886",
        to="whatsapp:+919818584627"
    )

    print("WhatsApp Sent:", message.sid)

def parse_date(date_str):

    # Google format → Date(YYYY,MM,DD)
    if isinstance(date_str, str) and date_str.startswith("Date("):
        parts = date_str.replace("Date(", "").replace(")", "").split(",")

        year = int(parts[0])
        month = int(parts[1]) + 1
        day = int(parts[2])

        return datetime(year, month, day).date()

    return None
    
def get_all_rows():
    response = requests.get(SHEET_URL)
    text = response.text
    json_data = json.loads(text[47:-2])

    data = []

    for r in json_data['table']['rows']:
        row = []
        for c in r['c']:
            row.append(c['v'] if c else "")
        data.append(row)

    return data

if __name__ == "__main__":
    print("Server + Scheduler running...")
    app.run(debug=True)