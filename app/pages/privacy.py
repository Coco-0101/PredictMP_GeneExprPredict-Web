"""
Privacy & data retention notice
"""

import streamlit as st

from core.storage import RETENTION_DAYS

days = f"{RETENTION_DAYS:g}"

st.title("Privacy & Data Retention")

st.markdown(f"""
### What we store
- Files you upload and the results computed from them
  are saved on our server in a folder named by a random **Session UUID**.
- We do not ask for your name, e-mail, or any account information, and we do not use cookies for tracking.

### How long we keep it
- Every session folder is **deleted automatically {days} days** after its last activity.
  Uploaded files and results cannot be recovered after that.
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
