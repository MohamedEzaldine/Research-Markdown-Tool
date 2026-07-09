import sys
import os
import re
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, 
                             QLabel, QFileDialog, QMessageBox, QProgressBar, QTextEdit)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QTextCursor

# ---------------------------------------------------------
# التقاط مخرجات النظام (Terminal) لعرضها في الواجهة
# ---------------------------------------------------------
class StreamInterceptor(QObject):
    text_written = pyqtSignal(str)
    def write(self, text):
        self.text_written.emit(str(text))
    def flush(self):
        pass

# ---------------------------------------------------------
# كلاس المعالجة المحلية
# ---------------------------------------------------------
class LocalConverterThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, pdf_path, save_path):
        super().__init__()
        self.pdf_path = pdf_path
        self.save_path = save_path

    def run(self):
        try:
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict
            
            print("[نظام] جاري تهيئة نماذج الذكاء الاصطناعي...")
            converter = PdfConverter(artifact_dict=create_model_dict())
            
            print("[نظام] جاري تحليل الجداول والمعادلات واستخراج النص...")
            print("[نظام] الرجاء الانتظار، قد تستغرق العملية بعض الوقت حسب حجم الملف...")
            
            rendered = converter(self.pdf_path)
            full_text = rendered.markdown

            print("[نظام] جاري حفظ الملف النهائي...")
            with open(self.save_path, "w", encoding="utf-8") as f:
                f.write(full_text)
                
            self.finished.emit("تم التحويل بنجاح تام!")
        except Exception as e:
            self.error.emit(str(e))

# ---------------------------------------------------------
# الواجهة العصرية
# ---------------------------------------------------------
class ProConverterApp(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.setup_logging()

    def initUI(self):
        self.setWindowTitle('المحول البحثي الاحترافي (Pro Edition)')
        self.setGeometry(200, 200, 550, 450)
        
        # تصميم (CSS) للواجهة لتبدو عصرية جداً
        self.setStyleSheet("""
            QWidget { background-color: #f8f9fa; font-family: 'Segoe UI', Tahoma; }
            QLabel { color: #2c3e50; font-size: 14px; font-weight: bold; }
            QPushButton { 
                background-color: #2980b9; color: white; border-radius: 6px; 
                padding: 10px; font-size: 13px; font-weight: bold;
            }
            QPushButton:hover { background-color: #3498db; }
            QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }
            QProgressBar { 
                border: 1px solid #bdc3c7; border-radius: 5px; text-align: center; color: #2c3e50; font-weight: bold;
            }
            QProgressBar::chunk { background-color: #27ae60; border-radius: 4px; }
            QTextEdit { 
                background-color: #1e272e; color: #2ecc71; border-radius: 6px; 
                padding: 5px; font-family: Consolas, monospace; font-size: 12px;
            }
        """)
        
        layout = QVBoxLayout()
        
        self.info_label = QLabel('اختر ملف PDF لتحويله إلى Markdown بدقة فائقة', self)
        self.info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.info_label)

        self.btn_select = QPushButton('📂 استعراض واختيار ملف PDF', self)
        self.btn_select.clicked.connect(self.select_file)
        layout.addWidget(self.btn_select)

        self.file_label = QLabel('', self)
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setStyleSheet("color: #e67e22; font-size: 12px;")
        layout.addWidget(self.file_label)

        # شاشة الأوامر (Console)
        self.console_output = QTextEdit(self)
        self.console_output.setReadOnly(True)
        self.console_output.setPlaceholderText("سجل العمليات سيظهر هنا...")
        layout.addWidget(self.console_output)

        # شريط التقدم
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.btn_convert = QPushButton('🚀 بدء التحويل الذكي', self)
        self.btn_convert.clicked.connect(self.start_conversion)
        self.btn_convert.setEnabled(False)
        self.btn_convert.setStyleSheet("background-color: #27ae60;")
        layout.addWidget(self.btn_convert)

        self.setLayout(layout)
        self.pdf_path = ""

    def setup_logging(self):
        # تحويل مخرجات النظام إلى الواجهة
        self.interceptor = StreamInterceptor()
        self.interceptor.text_written.connect(self.append_log)
        sys.stdout = self.interceptor
        sys.stderr = self.interceptor

    def append_log(self, text):
        if text.strip():
            self.console_output.moveCursor(QTextCursor.End)
            self.console_output.insertPlainText(text)
            self.console_output.moveCursor(QTextCursor.End)
            # محاولة محاكاة شريط التقدم بناءً على المخرجات
            if "%" in text:
                try:
                    # البحث عن أي رقم متبوع بعلامة %
                    match = re.search(r'(\d+)%', text)
                    if match:
                        self.progress_bar.setValue(int(match.group(1)))
                except:
                    pass

    def select_file(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "اختر PDF", "", "PDF Files (*.pdf)", options=options)
        if file_path:
            self.pdf_path = file_path
            self.btn_convert.setEnabled(True)
            self.file_label.setText(f"تم التحديد: {os.path.basename(file_path)}")

    def start_conversion(self):
        if not self.pdf_path: return
            
        options = QFileDialog.Options()
        default_name = os.path.splitext(os.path.basename(self.pdf_path))[0] + "_Converted.md"
        save_path, _ = QFileDialog.getSaveFileName(self, "حفظ ملف كـ", default_name, "Markdown Files (*.md)", options=options)
        
        if save_path:
            self.btn_select.setEnabled(False)
            self.btn_convert.setEnabled(False)
            self.progress_bar.show()
            self.progress_bar.setRange(0, 0) # حركة مستمرة في البداية
            self.console_output.clear()
            
            self.converter_thread = LocalConverterThread(self.pdf_path, save_path)
            self.converter_thread.finished.connect(lambda msg: self.done(msg))
            self.converter_thread.error.connect(lambda msg: self.done(msg, error=True))
            self.converter_thread.start()

    def done(self, msg, error=False):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.btn_select.setEnabled(True)
        if error: 
            QMessageBox.critical(self, "خطأ", f"حدثت مشكلة:\n{msg}")
            self.file_label.setText("فشل التحويل.")
        else: 
            QMessageBox.information(self, "نجاح", msg)
            self.file_label.setText("تم الانتهاء بنجاح.")
            self.btn_convert.setEnabled(False)

# ---------------------------------------------------------
# دالة التحميل المخفية (تستخدم أثناء التثبيت فقط)
# ---------------------------------------------------------
def download_models_only():
    print("جاري تحميل نماذج الذكاء الاصطناعي الأساسية، يرجى الانتظار...")
    from marker.models import create_model_dict
    create_model_dict()
    print("تم التحميل بنجاح!")
    sys.exit(0)

if __name__ == '__main__':
    # إذا تم تمرير هذا الأمر من برنامج التثبيت (Installer)
    if len(sys.argv) > 1 and sys.argv[1] == '--download-models':
        download_models_only()
    else:
        app = QApplication(sys.argv)
        ex = ProConverterApp()
        ex.show()
        sys.exit(app.exec_())