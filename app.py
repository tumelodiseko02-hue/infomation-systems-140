
import sqlite3
import sys

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QPushButton
)
from PyQt5.QtCore import Qt


# Open the existing login database
conn = sqlite3.connect("login.sqlite")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setGeometry(598, 95, 700, 700)
        self.setWindowTitle("AGRICTRIAL")

        # Window background and default font
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F3F6F4;
            }

            QWidget {
                font-family: Arial;
            }
        """)

        self.initUI()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main heading
        label_login = QLabel("AGRICTRIAL")
        label_login.setAlignment(Qt.AlignCenter)
        label_login.setStyleSheet("""
            QLabel {
                font-size: 34px;
                font-weight: bold;
                color: #174A35;
                padding-bottom: 5px;
            }
        """)

        # Login subtitle
        subtitle = QLabel("Sign in to your account")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #66756D;
                padding-bottom: 20px;
            }
        """)

        # Username input
        self.username = QLineEdit()
        self.username.setPlaceholderText("Enter username")
        self.username.setFixedSize(320, 48)
        self.username.setStyleSheet("""
            QLineEdit {
                font-size: 17px;
                color: #24352C;
                background-color: white;
                border: 1px solid #C7D2CB;
                border-radius: 8px;
                padding-left: 12px;
            }

            QLineEdit:focus {
                border: 2px solid #287A52;
            }
        """)

        # PIN input
        self.pin = QLineEdit()
        self.pin.setPlaceholderText("Enter PIN")
        self.pin.setEchoMode(QLineEdit.Password)
        self.pin.setFixedSize(320, 48)
        self.pin.setStyleSheet("""
            QLineEdit {
                font-size: 17px;
                color: #24352C;
                background-color: white;
                border: 1px solid #C7D2CB;
                border-radius: 8px;
                padding-left: 12px;
            }

            QLineEdit:focus {
                border: 2px solid #287A52;
            }
        """)

        # Login button
        self.button = QPushButton("LOGIN")
        self.button.setFixedSize(320, 48)
        self.button.setCursor(Qt.PointingHandCursor)
        self.button.setStyleSheet("""
            QPushButton {
                font-size: 17px;
                font-weight: bold;
                color: white;
                background-color: #287A52;
                border: none;
                border-radius: 8px;
            }

            QPushButton:hover {
                background-color: #1E6040;
            }

            QPushButton:pressed {
                background-color: #164A30;
            }
        """)

        self.button.clicked.connect(self.login)
        self.pin.returnPressed.connect(self.login)

        # Result message
        self.message = QLabel("")
        self.message.setAlignment(Qt.AlignCenter)
        self.message.setWordWrap(True)
        self.message.setStyleSheet("""
            QLabel {
                font-size: 15px;
                color: #174A35;
                padding-top: 8px;
            }
        """)

        # Layout
        layout = QVBoxLayout()
        layout.addStretch(2)

        layout.addWidget(label_login, alignment=Qt.AlignCenter)
        layout.addWidget(subtitle, alignment=Qt.AlignCenter)
        layout.addSpacing(10)
        layout.addWidget(self.username, alignment=Qt.AlignCenter)
        layout.addSpacing(12)
        layout.addWidget(self.pin, alignment=Qt.AlignCenter)
        layout.addSpacing(18)
        layout.addWidget(self.button, alignment=Qt.AlignCenter)
        layout.addWidget(self.message, alignment=Qt.AlignCenter)

        layout.addStretch(2)

        central_widget.setLayout(layout)

    def login(self):
        name = self.username.text().strip()
        pin_text = self.pin.text().strip()

        if not name or not pin_text:
            self.message.setStyleSheet(
                "font-size: 15px; color: #B42318; padding-top: 8px;"
            )
            self.message.setText("Please enter your username and PIN.")
            return

        try:
            pin = int(pin_text)
        except ValueError:
            self.message.setStyleSheet(
                "font-size: 15px; color: #B42318; padding-top: 8px;"
            )
            self.message.setText("Your PIN must contain numbers only.")
            return

        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM details WHERE username = ? AND pin = ?",
            (name, pin)
        )

        user = cur.fetchone()

        if user:
            self.message.setStyleSheet(
                "font-size: 17px; font-weight: bold; "
                "color: #287A52; padding-top: 8px;"
            )
            self.message.setText(f"Welcome, {name}!")
        else:
            self.message.setStyleSheet(
                "font-size: 15px; color: #B42318; padding-top: 8px;"
            )
            self.message.setText("Incorrect username or PIN.")


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
