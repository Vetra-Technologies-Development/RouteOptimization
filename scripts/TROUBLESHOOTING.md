# Troubleshooting Guide

## Python Not Found Error

If you get "Python not found" error, try the following:

### Solution 1: Use Python Launcher (Recommended)
The script now tries `py` launcher first, which is the most reliable on Windows.

### Solution 2: Check Python Installation
1. Open a new PowerShell window
2. Run: `py --version` or `python --version`
3. If neither works, Python may not be in your PATH

### Solution 3: Add Python to PATH
1. Find your Python installation (usually in `C:\Users\YourName\AppData\Local\Programs\Python\`)
2. Add it to System PATH:
   - Right-click "This PC" > Properties
   - Advanced System Settings > Environment Variables
   - Edit "Path" variable
   - Add Python installation folder

### Solution 4: Use Full Path
If Python is installed but not in PATH, you can modify `scripts/start.ps1` to use the full path:
```powershell
$pythonCmd = "C:\Users\YourName\AppData\Local\Programs\Python\Python314\python.exe"
```

### Solution 5: Install Python
If Python is not installed:
1. Download from https://www.python.org/downloads/
2. **Important**: Check "Add Python to PATH" during installation
3. Or install from Microsoft Store: https://apps.microsoft.com/store/detail/python-311/9NRWMJP3717K

## Virtual Environment Issues

### Issue: "Activation script missing"
**Solution**: Delete the `venv` folder and run the start script again. It will recreate it.

### Issue: "pip not found"
**Solution**: Make sure Python is installed correctly and includes pip. Reinstall Python if needed.

## Port Already in Use

If you get "port already in use" error:
1. Run `.\scripts\stop.ps1` to stop any running server
2. Or change the port: `$env:PORT=8001; .\scripts\start.ps1`

## Permission Errors

If you get permission errors:
1. Run PowerShell as Administrator
2. Or set execution policy: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

## Still Having Issues?

1. Check Python version: `py --version` (should be 3.11 or later)
2. Check if pip works: `py -m pip --version`
3. Try running manually:
   ```powershell
   py -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   uvicorn main:app --reload --host 127.0.0.1 --port 8000
   ```


