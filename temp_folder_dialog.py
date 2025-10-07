
import tkinter as tk
from tkinter import filedialog
import sys

try:
    root = tk.Tk()
    root.withdraw()
    folder_path = filedialog.askdirectory(title="Select folder to process")
    root.destroy()
    
    if folder_path:
        print(folder_path)
    else:
        print("NO_FOLDER_SELECTED")
except Exception as e:
    print(f"ERROR: {str(e)}")
