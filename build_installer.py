import subprocess
import sys
import os

def build():
    script = os.path.join(os.path.dirname(__file__), "mimo_installer.py")
    icon = os.path.join(os.path.expanduser("~"), "MimoSessionViewer", "mimo.ico")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "MiMo Installer",
        "--distpath", os.path.join(os.path.expanduser("~"), "Desktop"),
        "--workpath", os.path.join(os.path.dirname(__file__), "build"),
        "--specpath", os.path.dirname(__file__),
        "--clean",
    ]

    if os.path.exists(icon):
        cmd.extend(["--icon", icon])

    cmd.append(script)

    print("Building MiMo Installer...")
    print(" ".join(cmd))
    result = subprocess.run(cmd)

    if result.returncode == 0:
        exe = os.path.join(os.path.expanduser("~"), "Desktop", "MiMo Installer.exe")
        if os.path.exists(exe):
            size_mb = os.path.getsize(exe) / (1024 * 1024)
            print(f"\nBuild successful!")
            print(f"Output: {exe}")
            print(f"Size: {size_mb:.1f} MB")
        else:
            print("\nBuild completed but EXE not found at expected path")
    else:
        print(f"\nBuild failed with exit code {result.returncode}")

if __name__ == "__main__":
    build()
