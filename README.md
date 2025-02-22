# RAT-SPYWARE
# Convert Python Script to EXE Without Console Using PyInstaller

## Prerequisites
Make sure you have Python and `pip` installed.

### Install PyInstaller
```sh
pip install pyinstaller
```

## Convert `shell.py` to EXE

### 1. Open Terminal and Navigate to the Script Directory
```sh
cd path/to/your/script
```

### 2. Generate EXE Without a Console Window
```sh
pyinstaller --onefile --noconsole SPYWARE.py
```

## Output
- The generated `.exe` file will be located in the `dist/` folder.

## Additional Options
- **Add an icon**: `--icon=your_icon.ico`
- **Hide the PyInstaller splash screen**: `--noconsole`
- **Specify output directory**: `--distpath ./output`

### Example Command with Icon
```sh
pyinstaller --onefile --windowed --icon=myicon.ico shell.py
```

## Notes
- Ensure all dependencies are installed before running the executable.
- If the EXE gets flagged as a virus, you may need to sign it or add it to antivirus exceptions.
