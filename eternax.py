import sys
import os
import re
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QFileDialog, QDialog, QTreeWidget, QTreeWidgetItem, QMessageBox
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
import yt_dlp
import json

# Define paths
ASSETS_PATH = f'C:\\Users\\{os.getlogin()}\\Documents\\EternaX\\assets'
CACHE_PATH = f'C:\\Users\\{os.getlogin()}\\Documents\\EternaX\\cache\\downloaded.json'
APP_ICON_PATH = os.path.join(ASSETS_PATH, 'eternax.ico')

def convert_size(size_in_bytes):
    """Convert size in bytes to KB, MB, or GB."""
    if size_in_bytes >= 1_000_000_000:  # GB
        return f"{size_in_bytes / 1_000_000_000:.2f} GB"
    elif size_in_bytes >= 1_000_000:  # MB
        return f"{size_in_bytes / 1_000_000:.2f} MB"
    elif size_in_bytes >= 1_000:  # KB
        return f"{size_in_bytes / 1_000:.2f} KB"
    else:  # Bytes
        return f"{size_in_bytes} Bytes"

class DownloadThread(QThread):
    progress_signal = pyqtSignal(str, str, int, int, str)

    def __init__(self, url, format_selected, quality, save_path, custom_filename):
        super().__init__()
        self.url = url
        self.format_selected = format_selected
        self.quality = quality
        self.save_path = save_path
        self.custom_filename = custom_filename
        self.cancelled = False
        self.file_name = None

    def run(self):
        try:
            ydl_opts = {
                'format': f'bestvideo[height<={self.quality}]+bestaudio/best[height<={self.quality}]' if self.quality != 'Auto' else 'best',
                'outtmpl': os.path.join(self.save_path, f"{self.custom_filename}.%(ext)s"),
                'progress_hooks': [self.progress_hook],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(self.url, download=True)
                self.file_name = os.path.join(self.save_path, f"{self.custom_filename}.{info_dict['ext']}")
                file_size = os.path.getsize(self.file_name)
                self.progress_signal.emit(self.file_name, 'Completed', file_size, file_size, '0 KB/s')
        except Exception as e:
            print(f"Error in DownloadThread: {e}")
            self.progress_signal.emit("Error", 'Error', 0, 0, '0 KB/s')

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            percent = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes', 0)
            speed = d.get('speed', 0)
            speed_str = convert_size(speed) if speed else "0 KB/s"
            self.progress_signal.emit(
                f"{d.get('filename', 'Unknown')}",
                'Downloading',
                percent,
                total,
                speed_str
            )

class AddToQueueDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle('Add to Queue')
        self.setGeometry(100, 100, 400, 300)
        self.create_widgets()

    def create_widgets(self):
        layout = QVBoxLayout(self)

        self.url_label = QLabel('YouTube URL:')
        self.url_entry = QLineEdit(self)

        self.filename_label = QLabel('Custom Filename:')
        self.filename_entry = QLineEdit(self)

        self.format_label = QLabel('File Format:')
        self.format_combo = QComboBox(self)
        self.format_combo.addItems(['MP4', 'MP3'])

        self.quality_label = QLabel('Video Quality:')
        self.quality_combo = QComboBox(self)

        self.save_location_label = QLabel('Save Location:')
        location_layout = QHBoxLayout()
        self.save_location_entry = QLineEdit(self)
        self.browse_button = QPushButton()
        self.browse_button.setIcon(QIcon(os.path.join(ASSETS_PATH, 'browse.png')))
        self.browse_button.setIconSize(QSize(15, 15))  # Set the icon size to 10x10
        self.browse_button.setFixedSize(15, 15)  # Set the button size to 10x10
        self.browse_button.clicked.connect(self.browse_location)
        location_layout.addWidget(self.save_location_entry)
        location_layout.addWidget(self.browse_button)

        self.get_quality_button = QPushButton('Get Quality List')
        self.get_quality_button.clicked.connect(self.get_quality_list)

        self.add_to_queue_button = QPushButton('Add to Queue')
        self.add_to_queue_button.clicked.connect(self.add_to_queue)

        layout.addWidget(self.url_label)
        layout.addWidget(self.url_entry)
        layout.addWidget(self.filename_label)
        layout.addWidget(self.filename_entry)
        layout.addWidget(self.format_label)
        layout.addWidget(self.format_combo)
        layout.addWidget(self.quality_label)
        layout.addWidget(self.quality_combo)
        layout.addWidget(self.save_location_label)
        layout.addLayout(location_layout)
        layout.addWidget(self.get_quality_button)
        layout.addWidget(self.add_to_queue_button)

    def browse_location(self):
        location = QFileDialog.getExistingDirectory(self, 'Select Directory')
        if location:
            self.save_location_entry.setText(location)

    def get_quality_list(self):
        url = self.url_entry.text()
        if url:
            try:
                ydl_opts = {'format': 'bestaudio/best', 'quiet': True}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=False)
                    formats = info_dict.get('formats', [])
                    quality_options = list(set([f"{f.get('height', 'Audio')}p" for f in formats if f.get('height')]))
                    quality_options.sort(key=lambda x: int(x.replace('p', '')), reverse=True)
                    quality_options.insert(0, "Auto")

                    self.quality_combo.clear()
                    self.quality_combo.addItems(quality_options)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to fetch quality list: {e}")
        else:
            QMessageBox.critical(self, "Error", "Please enter a valid URL.")

    def add_to_queue(self):
        url = self.url_entry.text()
        custom_filename = self.filename_entry.text()
        format_selected = self.format_combo.currentText()
        quality = self.quality_combo.currentText().split(' ')[0]  # Extract format ID or "Auto"
        save_path = self.save_location_entry.text()

        if url and custom_filename and format_selected in ['MP4', 'MP3']:
            if format_selected == 'MP3' and quality != "Auto":
                QMessageBox.information(self, "Info", "Only 'Auto' quality is allowed for MP3 format.")
                return

            self.parent.add_video_to_queue(url, format_selected, quality, save_path, custom_filename)
            self.close()
        else:
            QMessageBox.critical(self, "Error", "Please enter a valid URL, custom filename, and select a file format.")


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Settings')
        self.setGeometry(100, 100, 300, 200)
        self.create_widgets()

    def create_widgets(self):
        layout = QVBoxLayout(self)

        self.settings_label = QLabel('Settings')
        self.settings_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.author_label = QLabel('Author: @itzanhzz')
        self.version_label = QLabel('Version: DEMO 1.0.2')
        self.note = QLabel('This is an temporary GUI for the app basic, the better one will be released soon!')

        self.close_button = QPushButton('Close')
        self.close_button.clicked.connect(self.close)

        layout.addWidget(self.settings_label)
        layout.addWidget(self.author_label)
        layout.addWidget(self.version_label)
        layout.addWidget(self.note)
        layout.addWidget(self.close_button)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('DEMO - EternaX')
        self.setWindowIcon(QIcon(APP_ICON_PATH))  # Set the application icon
        self.setGeometry(100, 100, 800, 600)
        self.create_widgets()

        # List to keep track of download threads
        self.download_threads = []

    def create_widgets(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Load and set the icons
        add_to_queue_image = QPixmap(os.path.join(ASSETS_PATH, 'add.png')).scaled(45, 45, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        settings_image = QPixmap(os.path.join(ASSETS_PATH, 'settings.png')).scaled(45, 45, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

        top_bar_layout = QHBoxLayout()
        self.add_to_queue_button = QPushButton()
        self.add_to_queue_button.setIcon(QIcon(add_to_queue_image))
        self.add_to_queue_button.setIconSize(QSize(45, 45))  # Set the icon size
        self.add_to_queue_button.setFixedSize(45, 45)  # Set the button size

        self.settings_button = QPushButton()
        self.settings_button.setIcon(QIcon(settings_image))
        self.settings_button.setIconSize(QSize(45, 45))  # Set the icon size
        self.settings_button.setFixedSize(45, 45)  # Set the button size

        self.add_to_queue_button.clicked.connect(self.open_add_to_queue_dialog)
        self.settings_button.clicked.connect(self.open_settings_dialog)

        top_bar_layout.addWidget(self.add_to_queue_button)
        top_bar_layout.addWidget(self.settings_button)
        top_bar_layout.addStretch()

        self.queue_tree = QTreeWidget(self)
        self.queue_tree.setHeaderLabels(['Name', 'Status', 'Speed', 'Size'])

        # Set column width for the "Name" column based on factor x
        x = 1.5  # Example factor, adjust as needed
        total_width = self.queue_tree.width()
        self.queue_tree.setColumnWidth(0, int(total_width * x))  # Adjust the width as needed

        layout.addLayout(top_bar_layout)
        layout.addWidget(self.queue_tree)

    def open_add_to_queue_dialog(self):
        AddToQueueDialog(self).exec()

    def open_settings_dialog(self):
        SettingsDialog(self).exec()

    def add_video_to_queue(self, url, format_selected, quality, save_path, custom_filename):
        # Add a new row to the queue
        item = QTreeWidgetItem(['Pending...', 'Waiting', '0 KB/s', '0 KB'])
        self.queue_tree.addTopLevelItem(item)

        # Start a new download thread
        download_thread = DownloadThread(url, format_selected, quality, save_path, custom_filename)
        download_thread.progress_signal.connect(lambda file_name, status, percent, total, speed: self.update_queue(item, file_name, status, percent, total, speed))
        self.download_threads.append(download_thread)
        download_thread.start()

    def update_queue(self, item, file_name, status, percent, total, speed):
        if file_name == 'Error':
            item.setText(0, 'Error')
            item.setText(1, status)
            item.setText(2, speed)
            item.setBackground(0, Qt.GlobalColor.red)
            return

        item.setText(0, file_name)
        item.setText(1, status)
        item.setText(2, speed)
        item.setText(3, convert_size(total))
        item.setBackground(0, Qt.GlobalColor.green)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
