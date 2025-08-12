## macOS Installation Instructions

**Important:** macOS will prevent this app from running due to quarantine restrictions. 
Follow these steps after downloading:

1. Open Terminal (found in Applications → Utilities)
2. Navigate to your Downloads folder:
   ```bash
   cd ~/Downloads
   ```
3. Remove the quarantine flag from the downloaded zip:
   ```bash
   xattr -d com.apple.quarantine macos-arm64.zip
   ```
4. Now you can unzip `macos-arm64.zip` in the Finder and move the `Writingway` folder where your want. 
5. Start the application with the `Writingway` script in the `Writingway` folder.

**Notes:** 
- Removing the quarantine flag is required because the application is not signed. 
  Only proceed if you trust the site where you downloaded this file.
- Writeingway stores your data (Projects) and setting in the application's folder: `Writingway`.
