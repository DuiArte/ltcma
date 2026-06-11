"""Download long-history return datasets (raw) and inspect their structure.
Sources: Damodaran (1928+), Shiller (1871+), Ken French Data Library (1990+)."""
import os, io, zipfile
import requests

import paths as _paths
RAW = str(_paths.DATA / "longhistory" / "raw")
os.makedirs(RAW, exist_ok=True)
HDR = {"User-Agent": "Mozilla/5.0 (research; LTCMA build)"}

DOWNLOADS = {
    # Damodaran historical annual returns (S&P500, T-bill, T-bond, Baa, RE, gold)
    "damodaran_histret.xls":
        "https://pages.stern.nyu.edu/~adamodar/pc/datasets/histretSP.xls",
    # Shiller monthly S&P composite + CAPE since 1871
    "shiller_ie_data.xls":
        "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/downloads/ie_data.xls",
    # Ken French regional market factors (monthly)
    "french_Developed.zip":
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Developed_3_Factors_CSV.zip",
    "french_Developed_exUS.zip":
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Developed_ex_US_3_Factors_CSV.zip",
    "french_Europe.zip":
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Europe_3_Factors_CSV.zip",
    "french_Japan.zip":
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Japan_3_Factors_CSV.zip",
    "french_Emerging.zip":
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/Emerging_5_Factors_CSV.zip",
}

for fname, url in DOWNLOADS.items():
    dest = os.path.join(RAW, fname)
    try:
        r = requests.get(url, headers=HDR, timeout=60)
        r.raise_for_status()
        with open(dest, "wb") as f:
            f.write(r.content)
        print(f"OK   {fname:28s} {len(r.content):>10,} bytes")
        if fname.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                for n in z.namelist():
                    head = z.read(n).decode("latin-1", "ignore").splitlines()[:6]
                    print(f"       inside: {n}")
                    for ln in head:
                        print(f"         | {ln[:90]}")
    except Exception as e:
        print(f"FAIL {fname:28s} {e}")

print("\nRaw files in:", RAW)
