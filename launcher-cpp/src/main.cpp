#include <QApplication>
#include <QIcon>

#include "mainwindow.h"

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("Kirby Retro Launcher"));
    app.setApplicationVersion(QStringLiteral("0.1.0"));
    app.setOrganizationName(QStringLiteral("KirbyRetro"));
    app.setWindowIcon(QIcon(QStringLiteral(":/resources/app-icon.png")));
    app.setStyle(QStringLiteral("Fusion"));
    app.setStyleSheet(QStringLiteral(R"(
        QWidget { color: #e9e9e9; }
        QMainWindow, QDialog { background: #2d2d30; }
        QMenuBar, QMenu, QToolBar, QStatusBar { background: #383838; }
        QMenuBar::item:selected, QMenu::item:selected { background: #2f6ea5; }
        QMenu { border: 1px solid #4a4a4c; }
        QLineEdit, QComboBox { background: #262626; border: 1px solid #4a4a4c; padding: 3px 6px; }
        QTableWidget { background: #262626; alternate-background-color: #2b2b2d; gridline-color: #3a3a3c; }
        QTableWidget::item:selected { background: #2f6ea5; color: #ffffff; }
        QHeaderView::section { background: #383838; border: 0; border-right: 1px solid #4a4a4c; padding: 5px; }
        QPushButton { background: #383838; border: 1px solid #4a4a4c; padding: 4px 12px; }
        QPushButton:hover { background: #454548; }
        QPushButton:default { border-color: #2f6ea5; }
        QToolButton { padding: 4px 10px; }
        QToolButton:hover { background: #454548; }
        QToolBar QLabel { color: #9d9d9d; }
        QLabel { background: transparent; }
        QProgressDialog, QMessageBox { background: #2d2d30; }
        QProgressBar { background: #262626; border: 1px solid #4a4a4c; text-align: center; }
        QProgressBar::chunk { background: #2f6ea5; }
        QScrollBar:vertical { background: #2d2d30; width: 12px; }
        QScrollBar::handle:vertical { background: #4a4a4c; border-radius: 4px; min-height: 24px; }
        QScrollBar:horizontal { background: #2d2d30; height: 12px; }
        QScrollBar::handle:horizontal { background: #4a4a4c; border-radius: 4px; min-width: 24px; }
        QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
    )"));

    MainWindow window;
    window.show();
    return app.exec();
}
