import subprocess
import os

MIMO_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Mimo Projects")

def main():
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0

    subprocess.Popen(
        ["cmd", "/c", "mimo", "web"],
        cwd=MIMO_DIR,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

if __name__ == "__main__":
    main()
