"""
Privacy & data retention notice
"""

import streamlit as st

from core.storage import RETENTION_DAYS

days = f"{RETENTION_DAYS:g}"

st.title("Privacy & Data Retention")

st.markdown(f"""
### What we store
- Only the **results** computed from your files are saved on our server, in a folder named by a
  random **Session UUID**.
- Files you upload are not kept: they stay in server memory only while your page is open (freed a
  few minutes after you leave), and a copy made to run the analysis is deleted when it finishes.
- We do not ask for your name, e-mail, or any account information, and we do not use cookies for tracking.

### How long we keep it
- Every session folder is **deleted automatically {days} days** after its last activity.
  Results cannot be recovered after that.
- Download any results you want to keep before then.

### Who can see it
- Results can be reloaded only with the exact Session UUID. Anyone who has the UUID can open the
  results, so keep it private and do not post it publicly.
- Uploaded data is used only to run the analysis you requested. It is not shared, sold, or used
  for any other purpose.

### Recommendations
- Upload **de-identified** data only: replace sample IDs (FID / IID) with codes that cannot be
  linked to a person.
- Genotype data can be identifying even without names. Make sure you have the consent or approval
  required by your institution before uploading it.
""")
