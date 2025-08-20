import os, stat, subprocess, shutil

def relax_permissions(path: str):
    try:
        subprocess.run(["chmod", "-RN", path], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["chflags", "-R", "nouchg", path], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    for root, dirs, files in os.walk(path, topdown=True):
        for d in dirs:
            p = os.path.join(root, d)
            try: os.chmod(p, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)  
            except Exception: pass
        for f in files:
            p = os.path.join(root, f)
            try: os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)               
            except Exception: pass
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)       
    except Exception:
        pass

def relax_permissions_for_delete(target_dir: str):
    if not target_dir or not os.path.exists(target_dir):
        return

    try:
        subprocess.run(["chmod", "-RN", target_dir], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["chflags", "-R", "nouchg", target_dir], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    for root, dirs, files in os.walk(target_dir, topdown=True):
        for d in dirs:
            dp = os.path.join(root, d)
            try: os.chmod(dp, 0o700)  
            except Exception: pass
        for f in files:
            fp = os.path.join(root, f)
            try: os.chmod(fp, 0o600)  
            except Exception: pass
    try:
        os.chmod(target_dir, 0o700)  
    except Exception:
        pass

    parent = os.path.dirname(target_dir.rstrip(os.sep))
    if parent and os.path.exists(parent):
        try:

            subprocess.run(["chmod", "u+wx", parent], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["chmod", "-N", parent], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["chflags", "nouchg", parent], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.chmod(parent, 0o700)
        except Exception:
            pass


def safe_move(src: str, dst_dir: str):
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))

    if os.path.abspath(src) == os.path.abspath(dst):
        return  

    try:
        shutil.move(src, dst)
    except PermissionError:
        relax_permissions_for_delete(os.path.dirname(src))
        relax_permissions_for_delete(dst_dir)
        shutil.move(src, dst)

def _onerror_chmod_then_retry(func, path, excinfo):
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)  
    except Exception:
        pass
    try:
        func(path)
    except Exception:
        pass