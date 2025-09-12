import re, os

def norm(string):
    return (string or "").strip().lower()

def basename(path_or_name):
    return os.path.basename(path_or_name.replace("\\", "/"))

def extract_login_from_cell_text(cell_text):
   
    text = cell_text.strip()

    moss_name = re.search(r"([^\s()]+?\.\w+)\s*\(\d+%\)", text)
    filename = basename(moss_name.group(1)) if moss_name else basename(text)

    moss_login = re.search(r"^q\d+_([A-Za-z0-9._-]+)\.\w+$", filename, re.IGNORECASE)
    if moss_login:
        return moss_login.group(1)

    moss_dir = re.search(r"/submissions/([^/]+)/[^/]+\.\w+$", text.replace("\\", "/"), re.IGNORECASE)
    if moss_dir:
        return moss_dir.group(1)

    moss_fallback = re.search(r"^([A-Za-z0-9._-]+)\s*\(\d+%\)$", basename(text))
    if moss_fallback:
        return moss_fallback.group(1)

    stem = os.path.splitext(filename)[0]
    moss_stem = re.search(r"^q\d+_([A-Za-z0-9._-]+)$", stem, re.IGNORECASE)
    return moss_stem.group(1) if moss_stem else stem

def extract_percentage(cell_text: str):
    moss_percentage = re.search(r"\((\d+)%\)", cell_text)
    return int(moss_percentage.group(1)) if moss_percentage else None