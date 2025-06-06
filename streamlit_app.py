import streamlit as st
import pandas as pd
import requests
import io
import re
from datetime import datetime
from collections import defaultdict

st.title("📱 WhatsApp Expense Analyzer (OCR.Space Edition)")
st.write("Upload expense screenshots. Text will be extracted using OCR.Space API (free, no login).")

API_URL = "https://api.ocr.space/parse/image"
API_KEY = "helloworld"  # free demo key

def ocr_space_image(image_bytes):
    response = requests.post(
        API_URL,
        files={"filename": image_bytes},
        data={"apikey": API_KEY, "language": "eng"},
    )
    result = response.json()
    return result.get("ParsedResults", [{}])[0].get("ParsedText", "")

def extract_fields(text):
    amt_match = re.search(r"₹\s?(\d+[\d,]*)", text)
    amount = int(amt_match.group(1).replace(',', '')) if amt_match else None

    date_match = re.search(r"\d{1,2} \w+ \d{4},? \d{1,2}:\d{2}(?: [APap][Mm])?", text)
    try:
        date = datetime.strptime(date_match.group(), "%d %B %Y, %I:%M %p") if date_match else None
    except:
        date = None

    recp_match = re.search(r"To:? (.*)", text)
    recipient = recp_match.group(1).strip() if recp_match else ""

    comment_match = re.search(r"\n(.*?)(?=\n|$)", text)
    comment = comment_match.group(1).strip() if comment_match else ""

    return {
        "Date": date,
        "Amount": amount,
        "Recipient": recipient,
        "Comment": comment
    }

def categorize(text):
    categories = {
        "rapido": "Travel", "auto": "Travel",
        "zomato": "Food", "swiggy": "Food", "fooding": "Food",
        "hardware": "Material", "paint": "Material",
        "rent": "Housing", "bhupendra": "Personal", "aniket": "Travel"
    }
    for keyword, cat in categories.items():
        if keyword in text.lower():
            return cat
    return "Uncategorized"

def flag_entry(entry, seen_keys, recipient_times):
    flags = []
    key = (entry["Amount"], entry["Recipient"], entry["Date"])
    if key in seen_keys:
        flags.append("DUPLICATE")
    if not entry["Amount"] or not entry["Date"]:
        flags.append("MISSING DATA")
    if entry["Amount"] and (entry["Amount"] % 1000 == 0 or entry["Amount"] > 10000):
        flags.append("DUBIOUS (HIGH AMOUNT)")
    if entry["Date"] and (entry["Date"].hour < 6 or entry["Date"].hour > 22):
        flags.append("DUBIOUS (UNUSUAL TIME)")
    if entry["Recipient"] and entry["Date"]:
        times = recipient_times.get(entry["Recipient"], [])
        times = [t for t in times if abs((entry["Date"] - t).total_seconds()) < 3600]
        if times:
            flags.append("DUBIOUS (HIGH FREQUENCY)")
        times.append(entry["Date"])
        recipient_times[entry["Recipient"]] = times
    return flags

uploaded_files = st.file_uploader("Upload Images", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
    records = []
    seen = set()
    recipient_times = defaultdict(list)

    for uploaded_file in uploaded_files:
        image_bytes = uploaded_file.read()
        text = ocr_space_image(image_bytes)

        fields = extract_fields(text)
        fields["Category"] = categorize(text)
        fields["Source"] = uploaded_file.name
        fields["Flags"] = ", ".join(flag_entry(fields, seen, recipient_times))
        seen.add((fields["Amount"], fields["Recipient"], fields["Date"]))
        records.append(fields)

    df = pd.DataFrame(records)
    st.dataframe(df)

    output = io.BytesIO()
    df.to_excel(output, index=False)
    st.download_button(
        label="📥 Download Excel",
        data=output.getvalue(),
        file_name="whatsapp_expenses_ocrspace.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )