import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtCore import Qt
from ui.whale_pet_widget import WhaleLayeredPetWidget


def main():
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Round)
    app = QApplication(sys.argv)
    pet = WhaleLayeredPetWidget(target_height=260)
    pet.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
