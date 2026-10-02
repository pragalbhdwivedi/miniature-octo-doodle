"""Read-only Windows process-lifetime checks for the Antigravity sidecar host.

Uses public Windows process metadata, not editor endpoints or app credentials.
An orphaned timer must not reserve delivery against an exited host instance.
"""
import os


def valid_chain(processes, pid):
    child=processes.get(pid)
    if not child: return False
    for expected in ('language_server.exe','language_server.exe','antigravity.exe'):
        parent=processes.get(child.get('parent'))
        if (not parent or parent.get('name','').lower()!=expected
                or not child.get('born') or not parent.get('born')
                or parent['born']>child['born']):
            return False
        child=parent
    return True


def windows_process_chain(pid):
    import ctypes
    from ctypes import wintypes as w
    class Entry(ctypes.Structure):
        _fields_=[('dwSize',w.DWORD),('cntUsage',w.DWORD),('th32ProcessID',w.DWORD),
                  ('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',w.DWORD),
                  ('cntThreads',w.DWORD),('th32ParentProcessID',w.DWORD),
                  ('pcPriClassBase',w.LONG),('dwFlags',w.DWORD),('szExeFile',w.WCHAR*260)]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD]
    kernel.CreateToolhelp32Snapshot.restype=w.HANDLE
    kernel.Process32FirstW.argtypes=[w.HANDLE,ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes=[w.HANDLE,ctypes.POINTER(Entry)]
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]
    kernel.OpenProcess.restype=w.HANDLE
    kernel.GetProcessTimes.argtypes=[w.HANDLE]+[ctypes.POINTER(w.FILETIME)]*4
    kernel.CloseHandle.argtypes=[w.HANDLE]
    handle=kernel.CreateToolhelp32Snapshot(2,0)
    if handle==ctypes.c_void_p(-1).value: raise OSError('Process snapshot unavailable')
    rows={}
    try:
        entry=Entry();entry.dwSize=ctypes.sizeof(entry)
        found=kernel.Process32FirstW(handle,ctypes.byref(entry))
        while found:
            rows[entry.th32ProcessID]={'parent':entry.th32ParentProcessID,'name':entry.szExeFile}
            found=kernel.Process32NextW(handle,ctypes.byref(entry))
    finally: kernel.CloseHandle(handle)
    current=pid
    for _ in range(4):
        row=rows.get(current)
        if not row: break
        process=kernel.OpenProcess(0x1000,False,current)
        if not process: break
        try:
            born,exit_time,kernel_time,user_time=[w.FILETIME() for _ in range(4)]
            if not kernel.GetProcessTimes(process,*map(ctypes.byref,(born,exit_time,kernel_time,user_time))): break
            # Reject an exited process even if its handle/snapshot still exists.
            if exit_time.dwHighDateTime or exit_time.dwLowDateTime: break
            row['born']=(born.dwHighDateTime<<32)|born.dwLowDateTime
        finally: kernel.CloseHandle(process)
        current=row['parent']
    return rows


def active_host():
    if os.name!='nt': return False
    try: return valid_chain(windows_process_chain(os.getpid()),os.getpid())
    except (OSError,ValueError): return False
