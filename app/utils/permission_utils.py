import os, stat, shutil, time

def relax_permissions(path):

    if not path or not os.path.exists(path):
        return

    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD | (stat.S_IEXEC if os.path.isdir(path) else 0))
    except Exception:
        pass
   
    for root, dirs, files in os.walk(path, topdown=True):
        for d in dirs:
            p = os.path.join(root, d)
            try:
                os.chmod(p, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)  
            except Exception:
                pass
        for f in files:
            p = os.path.join(root, f)
            try:
                os.chmod(p, stat.S_IWRITE | stat.S_IREAD) 
            except Exception:
                pass

def relax_permissions_for_delete(target_dir):
 
    relax_permissions(target_dir)
    parent = os.path.dirname(target_dir.rstrip(os.sep))
    if parent and os.path.exists(parent):
        try:
            os.chmod(parent, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        except Exception:
            pass

def retry(func, *args, retries=4, delay=0.25, **kwargs):
    last = None
    for _ in range(retries):
        try:
            return func(*args, **kwargs)
        except PermissionError as e:
            last = e
            time.sleep(delay)
    if last:
        raise last

def safe_move(src, dst_dir):
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    if os.path.abspath(src) == os.path.abspath(dst):
        return


    if os.path.exists(dst):
        try:
            if os.path.isdir(dst):
                
                if not os.listdir(dst):
                    retry(os.rmdir, dst)
                elif os.path.isdir(src):
                    for name in os.listdir(src):
                        retry(shutil.move, os.path.join(src, name), dst)
                    retry(os.rmdir, src)
                    return
                else:
                    
                    maybe_file = os.path.join(dst, os.path.basename(src))
                    if os.path.isfile(maybe_file):
                        retry(os.remove, maybe_file)
            else:
                retry(os.remove, dst) 
        except PermissionError:
            relax_permissions_for_delete(dst)
            if os.path.isdir(dst) and not os.listdir(dst):
                retry(os.rmdir, dst)
            elif os.path.isfile(dst):
                retry(os.remove, dst)

    try:
        retry(shutil.move, src, dst)
    except PermissionError:
       
        relax_permissions_for_delete(os.path.dirname(src))
        relax_permissions_for_delete(dst_dir)
        retry(shutil.move, src, dst)


def _onerror_chmod_then_retry(func, path, excinfo):

    try:
        if os.path.isdir(path):
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)  # 0o700
        else:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)  # 0o600
        func(path)
    except Exception:
        pass