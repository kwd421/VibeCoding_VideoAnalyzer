import tkinter as tk
import os
import glob
from gui_app import CustomModelApp

def main():
    # 이전 작업 찌꺼기 청소
    for junk in glob.glob("*_temp.wav"):
        try: os.remove(junk)
        except: pass
    
    root = tk.Tk()
    # v16 기반의 복구된 앱 실행
    app = CustomModelApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
