import streamlit as st
import pdfplumber
import pandas as pd
import re

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="FinAnalyzer Pro", page_icon="📊", layout="wide")

# --- HELPER FUNCTIONS ---

def is_date(string):
    """Checks if a string looks like a date."""
    if not string: return False
    return re.search(r'^\d{2}[/-](?:\d{2}|[A-Za-z]{3})[/-]\d{2,4}', str(string))

def clean_amount(val):
    """Extracts numeric amount and Dr/Cr status."""
    if not val: return None, None
    val = str(val).strip()
    is_credit = "Cr" in val or "CR" in val or val.endswith("Cr")
    clean_val = val.replace(',', '').replace('Rs.', '').replace('Cr', '').replace('Dr', '').strip()
    try:
        numbers = re.findall(r"[\d,]+\.\d{2}", clean_val)
        if numbers:
            return float(numbers[-1].replace(',', '')), "Cr" if is_credit else "Dr"
    except:
        pass
    return None, None

def process_kotak(pdf_file, password=None):
    """Logic specific to Kotak Mahindra Bank PDFs."""
    transactions = []
    # Handle empty password string as None
    pwd = password if password else None
    
    try:
        with pdfplumber.open(pdf_file, password=pwd) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text", "snap_tolerance": 4})
                for table in tables:
                    for row in table:
                        clean_row = [str(c).strip() if c else "" for c in row]
                        if not any(clean_row): continue
                        
                        if is_date(clean_row[0]):
                            try:
                                date = clean_row[0]
                                amount = 0.0
                                txn_type = "Dr"
                                narration = ""
                                
                                for i in range(len(clean_row)-1, 0, -1):
                                    amt, dr_cr = clean_amount(clean_row[i])
                                    if amt is not None:
                                        amount = amt
                                        txn_type = dr_cr
                                        narration = " ".join([x for x in clean_row[1:i] if x])
                                        break
                                
                                if amount != 0.0:
                                    transactions.append({"Date": date, "Narration": narration, "Amount": amount, "Type": txn_type})
                            except: pass
    except Exception as e:
        st.error(f"Error processing Kotak PDF: {e}")
        return pd.DataFrame()
        
    return pd.DataFrame(transactions)

def process_generic(pdf_file, password=None):
    """Fallback logic for unknown banks."""
    transactions = []
    pwd = password if password else None

    try:
        with pdfplumber.open(pdf_file, password=pwd) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for line in text.split('\n'):
                        parts = line.split()
                        if not parts: continue
                        
                        if is_date(parts[0]):
                            try:
                                date = parts[0]
                                amt, dr_cr = clean_amount(parts[-1])
                                if amt is None and len(parts) > 1:
                                    amt, dr_cr = clean_amount(parts[-2])
                                
                                if amt is not None:
                                    narration = " ".join(parts[1:-1]).replace(str(amt), "")
                                    transactions.append({"Date": date, "Narration": narration, "Amount": amt, "Type": dr_cr})
                            except: pass
    except Exception as e:
        st.error(f"Error processing PDF (Generic): {e}")
        return pd.DataFrame()

    return pd.DataFrame(transactions)

# --- THE USER INTERFACE (UI) ---

st.title("📊 Universal Bank Statement Analyzer")
st.markdown("Convert messy PDF bank statements into clean Excel/CSV formats instantly.")

# Sidebar for controls
with st.sidebar:
    st.header("Upload Configuration")
    bank_choice = st.selectbox("Select Bank Format", ["Kotak Mahindra Bank", "Generic / Other Bank"])
    
    # ADDED: Password Input Field
    pdf_password = st.text_input("PDF Password (if any)", type="password", help="Leave blank if the file has no password")
    
    uploaded_file = st.file_uploader("Upload PDF Statement", type="pdf")

if uploaded_file:
    # Reset file pointer to be safe (good practice for Streamlit uploads)
    uploaded_file.seek(0)
    
    st.success("File Uploaded Successfully!")
    
    if st.button("Analyze Statement"):
        with st.spinner(f"Analyzing {bank_choice} Statement..."):
            if bank_choice == "Kotak Mahindra Bank":
                df = process_kotak(uploaded_file, password=pdf_password)
            else:
                df = process_generic(uploaded_file, password=pdf_password)
        
        # Show Results
        if not df.empty:
            st.divider()
            
            # Metric Cards
            col1, col2, col3 = st.columns(3)
            total_dr = df[df['Type'] == 'Dr']['Amount'].sum()
            total_cr = df[df['Type'] == 'Cr']['Amount'].sum()
            
            col1.metric("Total Transactions", len(df))
            col2.metric("Total Spends (Dr)", f"₹ {total_dr:,.2f}")
            col3.metric("Total Income (Cr)", f"₹ {total_cr:,.2f}")
            
            # Data Preview
            st.subheader("Extracted Data")
            st.dataframe(df, use_container_width=True)
            
            # Download Button
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name="converted_statement.csv",
                mime="text/csv",
            )
        else:
            st.warning("No transactions found. Check the password or try 'Generic' mode.")

else:
    st.info("👈 Please upload a PDF file from the sidebar to begin.")